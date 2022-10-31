from copy import deepcopy

SERVER_GCP_PROJECT = "broad-cho-priv1"
SERVER_REGION = "us-central1"
SERVER_ZONE = f"{SERVER_REGION}-a"
NETWORK_NAME = "secure-gwas"
SUBNET_NAME = f"{NETWORK_NAME}-subnet"
INSTANCE_NAME_ROOT = NETWORK_NAME
# PARAMETER_BUCKET = f"{NETWORK_NAME}-data"
# TEMP_FOLDER = "src/temp"
# PARAMETER_FILES = ["test.par.0.txt", "test.par.1.txt", "test.par.2.txt"]
# BASE_P = "1461501637330902918203684832716283019655932542929"
# DATA_VALIDATION_CONSTANT = 4 * len(BASE_P)
# DATA_VALIDATION_FILES = ["g.bin", "m.bin", "p.bin", "other_shared_key.bin", "pos.txt"]

MPCGWAS_SHARED_PARAMETERS = {
    "NUM_SNPS": {
        "name": "Number of SNPs",
        "description": "The number of SNPs (Single Nucleotide Polymorphisms) in the dataset.",
        "value": "1000",
    },
    "NUM_COVS": {
        "name": "Number of Covariates",
        "description": "The number of covariate features in the dataset.",
        "value": "10",
    },
    "NUM_DIM_TO_REMOVE": {
        "name": "Number of Dimensions to Remove",
        "description": "The number of principal components to correct for (in the PCA).",
        "value": "5",
    },
    "NUM_OVERSAMPLE": {
        "name": "Oversampling Parameter for PCA",
        "description": "An oversampling parameter for randomized principal component analysis: how many extra components should be extracted to improve the accuracy.",
        "value": "5",
    },
    "NUM_POWER_ITER": {
        "name": "Number of Power Iterations",
        "description": "The number of power iterations during the randomized PCA.",
        "value": "10",
    },
    "SKIP_QC": {
        "name": "Skip Quality Control",
        "description": "A binary value to skip quality control and use all individuals/SNPs.",
        "value": "0",
    },
    "IMISS_UB": {
        "name": "Individual Missing Rate UB",
        "description": "The individual missing rate upper bound.",
        "value": "0.05",
    },
    "HET_LB": {
        "name": "Heterozygosity LB",
        "description": "The individual heterozygosity lower bound.",
        "value": "0.2",
    },
    "HET_UB": {
        "name": "Heterozygosity UB",
        "description": "The individual heterozygosity upper bound.",
        "value": "0.5",
    },
    "GMISS_UB": {
        "name": "Genotype Missing Rate UB",
        "description": "The genotype missing rate upper bound.",
        "value": "0.1",
    },
    "MAF_LB": {
        "name": "Minor Allele Frequency LB",
        "description": "The minor allele frequency lower bound.",
        "value": "0",
    },
    "MAF_UB": {
        "name": "Minor Allele Frequency UB",
        "description": "The minor allele frequency upper bound.",
        "value": "1",
    },
    "HWE_UB": {
        "name": "Hardy Weinberg Equilibrium UB",
        "description": "The hardy weinberg equilibrium test statistic upper bound.",
        "value": "100000",
    },
    "LD_DIST_THRES": {
        "name": "LD Distance Threshold",
        "description": "The genomic distance threshold for selecting SNPs for principal component analysis.",
        "value": "1",
    },
    "index": [
        "NUM_SNPS",
        "NUM_COVS",
        "NUM_DIM_TO_REMOVE",
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

MPCGWAS_ADVANCED_PARAMETERS = {
    "ITER_PER_EVAL": {
        "name": "Iterations per Evaluation",
        "description": "The number of QR iterations per eigenvalue when performing eigendecomposition.",
        "value": "5",
    },
    "NUM_OVERSAMPLE": {
        "name": "Oversampling Parameter for PCA",
        "description": "An oversampling parameter for randomized principal component analysis: how many extra components should be extracted to improve the accuracy.",
        "value": "5",
    },
    "NUM_POWER_ITER": {
        "name": "Number of Power Iterations",
        "description": "The number of power iterations during the randomized PCA.",
        "value": "10",
    },
    "NBIT_K": {
        "name": "NBIT_K",
        "description": "Total number of bits used to represent data values",
        "value": "60",
    },
    "NBIT_F": {
        "name": "NBIT_F",
        "description": "Number of bits assigned to the fractional range",
        "value": "30",
    },
    "NBIT_V": {
        "name": "NBIT_V",
        "description": "Number of additional bits used as a buffer for statistical security",
        "value": "64",
    },
    "BASE_P": {
        "name": "BASE_P",
        "description": "Base prime used for cryptography (default is the largest 160 bit prime)",
        "value": "1461501637330902918203684832716283019655932542929",
    },
    "index": [
        "ITER_PER_EVAL",
        "NUM_OVERSAMPLE",
        "NUM_POWER_ITER",
        "NBIT_K",
        "NBIT_F",
        "NBIT_V",
        "BASE_P",
    ],
}

PCA_SHARED_PARAMETERS = {
    "NUM_SNPS": {
        "name": "Number of SNPs",
        "description": "The number of SNPs (Single Nucleotide Polymorphisms) in the dataset.",
        "value": "1000",
    },
    "ITER_PER_EVAL": {
        "name": "Iterations per Evaluation",
        "description": "The number of QR iterations per eigenvalue when performing eigendecomposition.",
        "value": "5",
    },
    "NUM_DIM_TO_REMOVE": {
        "name": "Number of Dimensions to Remove",
        "description": "The number of principal components to correct for (in the PCA).",
        "value": "5",
    },
    "NUM_OVERSAMPLE": {
        "name": "Oversampling Parameter for PCA",
        "description": "An oversampling parameter for randomized principal component analysis: how many extra components should be extracted to improve the accuracy.",
        "value": "5",
    },
    "NUM_POWER_ITER": {
        "name": "Number of Power Iterations",
        "description": "The number of power iterations during the randomized PCA.",
        "value": "10",
    },
    "SKIP_QC": {
        "name": "Skip Quality Control",
        "description": "A binary value to skip quality control and use all individuals/SNPs.",
        "value": "0",
    },
    "IMISS_UB": {
        "name": "Individual Missing Rate UB",
        "description": "The individual missing rate upper bound.",
        "value": "0.05",
    },
    "HET_LB": {
        "name": "Heterozygosity LB",
        "description": "The individual heterozygosity lower bound.",
        "value": "0.2",
    },
    "HET_UB": {
        "name": "Heterozygosity UB",
        "description": "The individual heterozygosity upper bound.",
        "value": "0.5",
    },
    "GMISS_UB": {
        "name": "Genotype Missing Rate UB",
        "description": "The genotype missing rate upper bound.",
        "value": "0.1",
    },
    "MAF_LB": {
        "name": "Minor Allele Frequency LB",
        "description": "The minor allele frequency lower bound.",
        "value": "0",
    },
    "MAF_UB": {
        "name": "Minor Allele Frequency UB",
        "description": "The minor allele frequency upper bound.",
        "value": "1",
    },
    "HWE_UB": {
        "name": "Hardy Weinberg Equilibrium UB",
        "description": "The hardy weinberg equilibrium test statistic upper bound.",
        "value": "100000",
    },
    "LD_DIST_THRES": {
        "name": "LD Distance Threshold",
        "description": "The genomic distance threshold for selecting SNPs for principal component analysis.",
        "value": "1",
    },
    "index": [
        "NUM_SNPS",
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

SHARED_PARAMETERS = {
    "MPCGWAS": MPCGWAS_SHARED_PARAMETERS,
    "PCA": PCA_SHARED_PARAMETERS,
    # "SFGWAS": SFGWAS_SHARED_PARAMETERS,
}

ADVANCED_PARAMETERS = {
    "MPCGWAS": MPCGWAS_ADVANCED_PARAMETERS,
    # "PCA": PCA_ADVANCED_PARAMETERS,
    # "SFGWAS": SFGWAS_ADVANCED_PARAMETERS,
}


DEFAULT_USER_PARAMETERS = {
    "PUBLIC_KEY": {
        "name": "Public Key",
        "description": "Your public cryptographic key that you and the other participant will use to encrypt each of your data (combined with your respective private keys, of course).",
        "value": "",
    },
    "GCP_PROJECT": {
        "name": "GCP Project ID",
        "description": "The Project ID for the GCP project you're using (the one where you put your encrypted data and the VM instance will run).  \
        If you don't have a dedicated GCP project for this workflow, you will need to make one.  Note that this Project ID MAY or MAY NOT be the same as your Project Name.",
        "value": "",
    },
    "DATA_PATH": {
        "name": "GCP Path to Data",
        "description": "The path to your data in the GCP bucket.  For example, if I put the 'for_gwas' folder in a bucket called 'secure-gwas-data', \
            the the path would be 'secure-gwas-data/for_gwas'.",
        "value": "",
    },
    "GENO_BINARY_FILE_PREFIX": {
        "name": "Genotype Binary File Prefix",
        "description": "Path to the genotype binary file prefix (e.g. 'for_sfgwas/lung/pgen_converted/party1/geno/lung_party1_chr%d').",
        "value": "",
    },
    "NUM_INDS": {
        "name": "Number of Individuals",
        "description": "The number of individuals in your dataset.",
        "value": "",
    },
    "NUM_THREADS": {
        "name": "Number of Threads",
        "description": "The number of threads to use when running the GWAS",
        "value": "20",
    },
    "NUM_CPUS": {
        "name": "Number of CPUs",
        "description": "The number of CPUs to allocate to the VM instance that will be running the GWAS protocol in your GCP account.  \
        The number of GB of memory will automatically be set to 8x this number, as we are using Google's E2 high-memory VM instance.",
        "value": "16",
    },
    "ZONE": {
        "name": "Zone",
        "description": "The zone where you want to run your VM instance.",
        "value": "us-central1-a",
    },
    "BOOT_DISK_SIZE": {
        "name": "Boot Disk Size",
        "description": "The size of the boot disk for your VM instance. Must be at least 10GB.",
        "value": "10",
    },
    "CONFIGURE_STUDY_GCP_SETUP_MODE": {
        "name": "Configure Study GCP Setup Mode",
        "description": "A binary value to determine who sets up the GCP project for the user: Website | User.",
        "value": "",
    },
    "DATA_HASH": {
        "name": "Data Hash",
        "description": "The hash of the data you are using.  This is used to ensure that you are using the same data that you uploaded.",
        "value": "",
    },
    "IP_ADDRESS": {
        "name": "IP Address",
        "description": "The IP address of the VM instance that will be running the GWAS protocol.",
        "value": "",
    },
    "PORTS": {
        "name": "Ports",
        "description": "The ports (comma separated) used by the VM instance that will be running the GWAS protocol.",
        "value": "null,8001,8002",
    },
    "SA_EMAIL": {
        "name": "Service Account Email",
        "description": "The service account email used to connect to the server in the workflow where the user uses the cli.",
        "value": "",
    },
    "index": [
        "PUBLIC_KEY",
        "GCP_PROJECT",
        "DATA_PATH",
        "GENO_BINARY_FILE_PREFIX",
        "NUM_INDS",
        "NUM_THREADS",
        "NUM_CPUS",
        "ZONE",
        "BOOT_DISK_SIZE",
        "CONFIGURE_STUDY_GCP_SETUP_MODE",
        "DATA_HASH",
        "IP_ADDRESS",
        "PORTS",
        "SA_EMAIL",
    ],
}


def default_user_parameters(study_type: str) -> dict:
    if study_type == "MPCGWAS":
        return deepcopy(DEFAULT_USER_PARAMETERS)
    elif study_type in {"PCA", "SFGWAS"}:
        pars = deepcopy(DEFAULT_USER_PARAMETERS)
        pars["PORTS"]["value"] = "null,8020,8040"
        return pars
    else:
        raise ValueError(f"Unknown study type: {study_type}")


def broad_user_parameters() -> dict:
    parameters = deepcopy(DEFAULT_USER_PARAMETERS)
    parameters["GCP_PROJECT"]["value"] = SERVER_GCP_PROJECT
    parameters["NUM_INDS"]["value"] = "0"
    return parameters


BROAD_VM_SOURCE_IP_RANGES = [
    "69.173.112.0/21",
    "69.173.127.232/29",
    "69.173.127.128/26",
    "69.173.127.0/25",
    "69.173.127.240/28",
    "69.173.127.224/30",
    "69.173.127.230/31",
    "69.173.120.0/22",
    "69.173.127.228/32",
    "69.173.126.0/24",
    "69.173.96.0/20",
    "69.173.64.0/19",
    "69.173.127.192/27",
    "69.173.124.0/23",
    "10.0.0.10",  # other VMs doing the computation
    "10.0.1.10",
    "10.0.2.10",
    "35.235.240.0/20",  # IAP TCP forwarding
]
