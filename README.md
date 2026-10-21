# Family wealth by parents’ education

We plot **median family net worth in constant 2025 dollars**, comparing two parental education groups: **BA or more** and **HS or less**, in the 2016, 2019, 2022, and 2025 Survey of Consumer Finances (SCF).

Groups use the higher education level of the reference person’s mother or father. Families whose highest parental education is some college or an associate degree are excluded; there is no age restriction. Shading shows approximate 95% confidence intervals accounting for survey sampling and imputation. The comparisons are descriptive, not adjusted for age or other characteristics.

The latest figure is [`output/two_groups/wealth_by_parent_education_two_groups.png`](output/two_groups/wealth_by_parent_education_two_groups.png), with an SVG version alongside it. `estimates.csv` contains the plotted values and intervals; `validation.json` records sample checks.

## Data

Data come from the Federal Reserve Board’s [SCF website](https://www.federalreserve.gov/econres/scfindex.htm): full public microdata, summary extracts, bootstrap replicate weights, and codebooks for each wave. Parental education was first collected in **2016**, so this comparison cannot extend back to 1989. Dollar values use the Fed’s extracts expressed in 2025 dollars.

`get_data.py` downloads and caches the official files in `data/raw/` and writes a manifest with source URLs and SHA-256 hashes.

## Rerun

With Python 3 and `curl` installed, run from this project directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python get_data.py
python plot_two_groups.py
```

To redownload cached data, run `python get_data.py --refresh`. The plot averages weighted medians across the five SCF imputations and uses 999 bootstrap replicates for uncertainty.

The earlier four-group figure can also be reproduced with `python plot.py`; its results are saved directly in `output/`.
