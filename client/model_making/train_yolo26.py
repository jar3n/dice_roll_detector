import argparse
import random
import shutil
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CODE_ROOT = ROOT.parent
sys.path = [p for p in sys.path if Path(p).resolve() != CODE_ROOT]

PROJECT_DATA = Path(__file__).resolve().parents[3] / "data"

import yaml

from ultralytics import YOLO

IMG_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def collect_samples(data_yaml):
    data = yaml.safe_load(data_yaml.read_text())
    image_dir = data_yaml.parent / "images"
    label_dir = data_yaml.parent / "labels"

    samples = []
    for label_file in sorted(label_dir.glob("*.txt")):
        lines = label_file.read_text().strip().splitlines()
        if not lines:
            continue
        first_class = int(lines[0].split()[0])
        image_file = None
        for suffix in IMG_SUFFIXES:
            candidate = image_dir / (label_file.stem + suffix)
            if candidate.exists():
                image_file = candidate
                break
        if image_file is None:
            continue
        samples.append((image_file, label_file, first_class))
    return samples


def build_normalized_dataset(data_yaml, work_dir):
    samples = collect_samples(data_yaml)
    old_to_new = {}
    for _, _, cls in samples:
        old_to_new.setdefault(cls, len(old_to_new))

    dataset_dir = work_dir / "dataset"
    images_out = dataset_dir / "images"
    labels_out = dataset_dir / "labels"
    images_out.mkdir(parents=True, exist_ok=True)
    labels_out.mkdir(parents=True, exist_ok=True)

    normalized = []
    for image_file, label_file, _ in samples:
        link = images_out / image_file.name
        if not link.exists():
            link.symlink_to(image_file)
        out = labels_out / label_file.name
        remapped = []
        new_class = None
        for line in label_file.read_text().strip().splitlines():
            tokens = line.split()
            if not tokens:
                continue
            tokens[0] = str(old_to_new[int(tokens[0])])
            new_class = int(tokens[0])
            remapped.append(" ".join(tokens))
        out.write_text("\n".join(remapped) + ("\n" if remapped else ""))
        normalized.append((image_file, link, label_file, new_class))

    names = {new: str(old) for old, new in sorted(old_to_new.items(), key=lambda kv: kv[1])}
    data = {
        "path": str(dataset_dir.resolve()),
        "train": "images",
        "val": "images",
        "nc": len(names),
        "names": names,
    }
    (dataset_dir / "data.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    return dataset_dir, normalized


def stratify(samples, k, seed):
    rng = random.Random(seed)
    groups = defaultdict(list)
    for i, sample in enumerate(samples):
        groups[sample[3]].append(i)
    folds = [[] for _ in range(k)]
    for cls in sorted(groups):
        items = groups[cls]
        rng.shuffle(items)
        for j, idx in enumerate(items):
            folds[j % k].append(idx)
    splits = []
    for j in range(k):
        val = set(folds[j])
        train = [i for i in range(len(samples)) if i not in val]
        splits.append((train, sorted(val)))
    return splits


def write_image_list(path, indices, samples):
    path.write_text("".join(str(samples[i][1]) + "\n" for i in indices))


def build_fold_data(dataset_dir, fold_dir, train_idx, val_idx, samples):
    fold_dir.mkdir(parents=True, exist_ok=True)
    train_txt = fold_dir / "train.txt"
    val_txt = fold_dir / "val.txt"
    write_image_list(train_txt, train_idx, samples)
    write_image_list(val_txt, val_idx, samples)
    data_yaml = dataset_dir / "data.yaml"
    data = yaml.safe_load(data_yaml.read_text())
    fold_data = dict(data)
    fold_data["train"] = str(train_txt)
    fold_data["val"] = str(val_txt)
    fold_yaml = fold_dir / "data.yaml"
    fold_yaml.write_text(yaml.safe_dump(fold_data, sort_keys=False))
    return fold_yaml


def train_and_eval(fold_yaml, model_name, epochs, imgsz, device, project, name, seed):
    model = YOLO(model_name)
    model.train(
        data=str(fold_yaml),
        epochs=epochs,
        imgsz=imgsz,
        device=device,
        project=str(project),
        name=name,
        exist_ok=True,
        seed=seed,
        patience=30,
    )
    best = str(project / name / "weights" / "best.pt")
    model = YOLO(best)
    metrics = model.val(data=str(fold_yaml), project=str(project), name=name, exist_ok=True)
    box = metrics.box
    return {
        "name": name,
        "mAP50_95": float(box.map),
        "mAP50": float(box.map50),
        "precision": float(box.mp),
        "recall": float(box.mr),
        "best": best,
    }


def mean(values):
    return sum(values) / len(values)


def main():
    parser = argparse.ArgumentParser(description="Train YOLO26 with stratified k-fold CV")
    parser.add_argument("--data", type=Path,
                        default=PROJECT_DATA / "cv_work" / "dataset" / "data.yaml",
                        help="data.yaml of the normalized dataset (default: "
                             "<project>/data/cv_work/dataset/data.yaml)")
    parser.add_argument("--model", type=str, default="yolo26n.pt")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workdir", type=Path, default=PROJECT_DATA / "cv_work",
                        help="Working directory for the normalized dataset, folds, and "
                             "CV runs (default: <project>/data/cv_work)")
    parser.add_argument("--out", type=Path, default=ROOT / "yolo26_dice.pt",
                        help="Where to copy the final weights "
                             "(default: <code>/client/model_making/yolo26_dice.pt)")
    args = parser.parse_args()

    work_dir = args.workdir.resolve()
    args.data = args.data.resolve()
    args.out = args.out.resolve()
    dataset_dir, samples = build_normalized_dataset(args.data, work_dir)
    print(f"Normalized {len(samples)} samples -> {dataset_dir}")

    splits = stratify(samples, args.k, args.seed)
    project = work_dir / "runs"
    results = []
    for fold, (train_idx, val_idx) in enumerate(splits):
        print(f"\n=== Fold {fold + 1}/{args.k}: {len(train_idx)} train, {len(val_idx)} val ===")
        fold_yaml = build_fold_data(dataset_dir, work_dir / f"fold_{fold + 1}", train_idx, val_idx, samples)
        row = train_and_eval(
            fold_yaml, args.model, args.epochs, args.imgsz, args.device, project, f"fold_{fold + 1}", args.seed
        )
        print(f"Fold {fold + 1}: mAP50-95={row['mAP50_95']:.4f} mAP50={row['mAP50']:.4f} "
              f"P={row['precision']:.4f} R={row['recall']:.4f}")
        results.append(row)

    print("\n=== Stratified {}-fold CV summary ===".format(args.k))
    print(f"{'metric':<12}{'mean':>10}{'std':>10}")
    for key in ("mAP50_95", "mAP50", "precision", "recall"):
        vals = [r[key] for r in results]
        print(f"{key:<12}{mean(vals):>10.4f}{statistics.pstdev(vals):>10.4f}")

    print("\n=== Final model trained on all data, validated on all data ===")
    all_idx = list(range(len(samples)))
    fold_yaml = build_fold_data(dataset_dir, work_dir / "final", all_idx, all_idx, samples)
    final = train_and_eval(fold_yaml, args.model, args.epochs, args.imgsz, args.device, project, "final", args.seed)
    print(f"Final: mAP50-95={final['mAP50_95']:.4f} mAP50={final['mAP50']:.4f} "
          f"P={final['precision']:.4f} R={final['recall']:.4f}")
    print(f"Final weights: {final['best']}")
    shutil.copy(final["best"], args.out)
    print(f"Saved final model to {args.out}")


if __name__ == "__main__":
    main()
