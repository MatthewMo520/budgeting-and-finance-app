def load_kaggle_training_data(filepath: str = "/app/data/User0_credit_card_transactions.csv"):
    df = pd.read_csv(filepath)

    df = df.dropna(subset=["Merchant Name", "Amount", "MCC"])
    df = df[df["Is Fraud?"] == "No"]

    df["Amount"] = df["Amount"].str.replace("$", "").str.replace(",", "").astype(float)
    df["category"] = df["MCC"].astype(str).apply(mcc_to_category)
    df["Merchant Name"] = df["Merchant Name"].astype(str)  # fix here

    names = df["Merchant Name"].tolist()
    categories = df["category"].tolist()

    print(f"Loaded {len(names)} training samples from Kaggle dataset")
    return names, categories