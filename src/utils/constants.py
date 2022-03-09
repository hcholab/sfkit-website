SERVER_GCP_PROJECT = "broad-cho-priv1"
ZONE = "us-central1-a"
REGION = "us-central1"
NETWORK_NAME = "secure-gwas"
SUBNET_NAME = "secure-gwas-subnet"
INSTANCE_NAME_ROOT = "secure-gwas"
BUCKET_NAME = "secure-gwas-data"
TEMP_FOLDER = "src/temp"
PARAMETER_FILES = ["test.par.0.txt", "test.par.1.txt", "test.par.2.txt"]
BASE_P = "1461501637330902918203684832716283019655932542929"
DATA_VALIDATION_CONSTANT = 4 * len(BASE_P)

DEFAULT_SHARED_PARAMETERS = {
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
        "description": "The path to your encrypted data in the GCP bucket.  For example, if I put the 'encrypted_data' folder in a bucket called 'secure-gwas-data', \
            the the path would be 'secure-gwas-data/encrypted_data'.",
        "value": "",
    },
    "NUM_INDS": {
        "name": "Number of Individuals",
        "description": "The number of individuals in your dataset.",
        "value": "1000",
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
        "value": "4",
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
    "index": [
        "PUBLIC_KEY",
        "GCP_PROJECT",
        "DATA_PATH",
        "NUM_INDS",
        "NUM_THREADS",
        "NUM_CPUS",
        "ZONE",
        "BOOT_DISK_SIZE",
    ],
}
