# FX Allocation Tool

Interactive Streamlit app for testing how changes in:

- Equity weight
- Government-bond currency allocation
- Government-bond tilts relative to COFER

affect the **total portfolio FX allocation**.

## Portfolio structure

- Equity: adjustable from 25% to 30%
- IG: fixed at 9%
- HY: fixed at 1%
- Government bonds: residual weight

Government bonds are allocated using COFER as the base distribution, with user-defined currency tilts.

## Tilt logic

Government-bond tilts must sum to zero.

The app uses a **balancing currency**:
- Choose which currency should absorb the residual.
- Enter tilts for the other currencies.
- The balancing currency tilt is calculated automatically.

Example:

- USD +5pp
- EUR selected as balancing currency
- EUR is automatically set to -5pp

## Current FX benchmark

| Currency | Weight |
|---|---:|
| USD | 63.0% |
| EUR | 20.0% |
| GBP | 5.0% |
| JPY | 5.0% |
| AUD | 3.5% |
| CAD | 3.5% |

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

1. Upload all repository files to GitHub.
2. Go to Streamlit Community Cloud.
3. Sign in with GitHub.
4. Create a new app from the existing repository.
5. Select:
   - Repository: `fx-allocation-tool`
   - Branch: `main`
   - Main file: `app.py`
6. Deploy.

For a private GitHub repository, Streamlit must be granted access to the private repository.
