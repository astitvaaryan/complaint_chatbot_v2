# data/

Place the Kaggle customer-support CSV here so the classifier can augment its keyword lists.

## How to get the file

1. Go to: https://www.kaggle.com/datasets/tobiasbueck/multilingual-customer-support-tickets
2. Download the dataset (requires a free Kaggle account).
3. Extract and rename the CSV file to:

   ```
   data/customer_support_tickets.csv
   ```

4. Restart the FastAPI server — the classifier picks it up automatically at startup.

## What happens without the CSV

The classifier falls back to its built-in base keyword dictionaries — everything still works.
The CSV only **adds more phrases** to each category to improve recall on unusual phrasings.
