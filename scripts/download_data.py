from datasets import load_dataset
from src import config


def main():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)

    #check if if the dataset already exists
    if config.DATASET_PATH.exists():
        print(f"Dataset already exists at {config.DATASET_PATH}. Skipping download.")
        return
    
    ds = load_dataset("openai/openai_humaneval", split="test")
    ds.to_json(str(config.DATASET_PATH))
    print(f"Saved {len(ds)} rows to {config.DATASET_PATH}")
    print("Columns:", ds.column_names)
    print("\nExample row:")
    row = ds[0]
    for key in ds.column_names:
        print(f"--- {key} ---\n{row[key]}\n")


if __name__ == "__main__":
    main()
