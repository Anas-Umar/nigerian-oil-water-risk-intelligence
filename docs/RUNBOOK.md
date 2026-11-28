# Runbook (step by step)

Everything is done in a web browser: GitHub and Google Colab. No software to install.

## 1. GitHub (about 10 minutes)

1. **Back up the old repository.** Open the old repository, click the green **Code** button, then **Download ZIP**.
   Save it somewhere on your computer. This is only a backup of your old work; never put it into the new project.
2. **Delete the old repository.** Old repository, **Settings**, scroll to the bottom, **Danger Zone**,
   **Delete this repository**, type its name to confirm. (The old public history contains the derived GeoPackage.
   Deleting is the simplest way to remove it for good.)
3. **Create the new repository.** Click **+** (top right), **New repository**. Name:
   `nigerian-oil-water-risk-intelligence`. Choose **Private**. Do **not** tick README, .gitignore or licence.
   Click **Create repository**.
4. **Create a token** (lets Colab upload for you). Profile picture, **Settings**, **Developer settings**,
   **Personal access tokens**, **Tokens (classic)**, **Generate new token (classic)**. Note: `nowri-upload`.
   Expiration: 7 days. Tick **repo** and **workflow**. Generate, then copy the token (starts with `ghp_`).
   Keep it private. Never paste it into chat, a file or anywhere except Colab's hidden token box.
   Paste **only the token** there, never other text. If a token is ever shown anywhere it should not be, delete it on
   the same page and create a new one.

## 2. Google Colab (about 45-60 minutes, mostly waiting)

1. Go to colab.research.google.com, **Upload**, choose `NOWRI_run_in_colab.ipynb`.
2. Run the cells top to bottom (click the play button on each, wait until it finishes).
3. Cell 3 (tests) should end with no failures. Cell 4 uploads the code to your private repository.
4. Cell 5B: if the automatic RiverATLAS download is blocked for you, download the 2.55 GB zip once in your browser, put it
   in Google Drive and set `RA_ZIP` to its path. You can reuse it in every future session.
5. Cell 6 is the regression with the CC BY 4.0 river data (RiverATLAS). It must say
   `Regression ... PASS (41/41 checks passed)`. If it says FAIL or stops with an error, stop and send the printed text.
6. Cell 7 runs the corrected analysis. Cell 7B saves the GeoPackage to your computer (keep it out of GitHub). Cell 8
   downloads the reports.
7. Run cell 4 again to upload the reports.
8. Optional test drive: cells T1-T8 at the end of the same notebook (tables, maps, "what is near here?").
   A **separate** notebook runs on a separate Colab computer and cannot see these files, so the stand-alone
   `NOWRI_test_drive.ipynb` asks you to upload the GeoPackage saved by cell 7B.

## Updating with a new zip (when I send one)

Run **Cell 1** again and choose the new `nowri_repo_v0.1.1.zip`. It overwrites the code and documents but keeps your
`reports/` folder and the GitHub link. Then run cells 2 and 3, **Cell 7** (about 15 seconds if the session is still
alive), **Cell 8**, and finally **Cell 4** to upload.

## 3. Finish

1. Send the printed summaries from cells 6 and 7.
2. Once the regression has passed, make the repository public: **Settings**, **Danger Zone**, **Change visibility**,
   **Make public**.
3. Delete the token: GitHub **Settings**, **Developer settings**, **Personal access tokens**, delete `nowri-upload`.

## Before ever releasing the GeoPackage

Read the OGIM licence recorded in `reports/state/run_manifest.json` (under `sources`) and resolve the HydroSHEDS
redistribution question in writing. Until then, share code and aggregate reports only.
