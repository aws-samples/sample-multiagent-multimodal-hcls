# Model Inference Agent — Notebooks

End-to-end pipeline from raw multimodal data to deployed ML models.

## Pipeline

| # | Notebook | Description |
|---|----------|-------------|
| 01 | `01_data_ingestion.ipynb` | Ingest raw Synthea Coherent data (FHIR clinical, FASTQ genomic, DICOM imaging) into AWS HealthLake, HealthOmics, and HealthImaging |
| 02 | `02_data_preprocessing.ipynb` | Merge and feature-engineer clinical, genomic, and imaging data into ML-ready CSVs (`final_clinical_df.csv`, `final_genomic_df.csv`, `final_imaging_df.csv`) |
| 03 | `03_autogluon_train_export.ipynb` | Train AutoGluon ensemble models for all 4 diseases and export to `models/exported/autogluon/` |
| 04 | `04_tabpfn_train_export.ipynb` | Train TabPFN foundation models for all 4 diseases and export to `models/exported/tabpfn/` |

## Data Flow

```
Raw Data (S3)                    Preprocessed (S3)              Trained Models
─────────────                    ─────────────────              ──────────────
clinical/ (FHIR)  ─┐             preprocessing/                models/exported/
genomic/ (FASTQ)   ├─ 01 → 02 → ├─ final_clinical_df.csv  → 03 → autogluon/
imaging/ (DICOM)  ─┘             ├─ final_genomic_df.csv   → 04 → tabpfn/
                                 └─ final_imaging_df.csv
```

## Prerequisites

- AWS account 123456789012 with access to `s3://synthea-coherent-data-multimodal/`
- SageMaker notebook instance or Studio with `pandas`, `autogluon`, `tabpfn` installed
- Reference: [Multimodal Data Analysis with AWS Health and ML Services](https://aws.amazon.com/blogs/industries/multimodal-data-analysis-with-aws-health-and-machine-learning-services/)
