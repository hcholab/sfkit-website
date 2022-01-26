SERVER_GCP_PROJECT = "broad-cho-priv1"
ZONE = "us-central1-a"
REGION = "us-central1"
NETWORK_NAME = "secure-gwas"
SUBNET_NAME = "secure-gwas-subnet"
INSTANCE_NAME_ROOT = "secure-gwas"
BUCKET_NAME = "secure-gwas-data"
TEMP_FOLDER = "src/temp"
PARAMETER_FILES = ["test.par.0.txt", "test.par.1.txt", "test.par.2.txt"]

DEFAULT_PARAMETERS = {
    "NUM_INDS": {"description": "number of individuals in the dataset", "value": 1000},
    "NUM_SNPS": {"description": "The number of SNPs in the dataset", "value": 1000},
    "NUM_COVS": {
        "description": "number of covariate features in the dataset",
        "value": 10,
    },
    "ITER_PER_EVAL": {
        "description": "number of QR iterations per eigenvalue when performing eigendecomposition",
        "value": 5,
    },
    "NUM_DIM_TO_REMOVE": {
        "description": "number of PCs (Principal Components) to correct for",
        "value": 5,
    },
    "NUM_OVERSAMPLE": {
        "description": "oversampling parameter for rand PCA",
        "value": 5,
    },
    "NUM_POWER_ITER": {
        "description": "number of power iterations for rand PCA",
        "value": 10,
    },
    "SKIP_QC": {
        "description": "skip quality control and use all individuals/SNPs",
        "value": 0,
    },
    "IMISS_UB": {"description": "individual missing rate upper bound", "value": 0.05},
    "HET_LB": {"description": "individual heterozygosity lower bound", "value": 0.2},
    "HET_UB": {"description": "individual heterozygosity upper bound", "value": 0.5},
    "GMISS_UB": {"description": "genotype missing rate upper bound", "value": 0.1},
    "MAF_LB": {"description": "minor allele frequency lower bound", "value": 0},
    "MAF_UB": {"description": "minor allele frequency upper bound", "value": 1},
    "HWE_UB": {
        "description": "hardy weinberg equilibrium test statistic upper bound",
        "value": 100000,
    },
    "LD_DIST_THRES": {
        "description": "genomic distance threshold for selecting SNPs for PCA",
        "value": 1,
    },
    "index": [
        "NUM_INDS",
        "NUM_SNPS",
        "NUM_COVS",
        "ITER_PER_EVAL",
        "NUM_DIM_TO_REMOVE",
        "NUM_OVERSAMPLE",
        "NUM_POWER_ITER",
        "SKIP_QC",
        "IMISS_UB",
        "HET_LB",
        "HET_UB",
        "GMISS_UB",
        "MAF_LB",
        "MAF_UB",
        "HWE_UB",
        "LD_DIST_THRES",
    ],
}
