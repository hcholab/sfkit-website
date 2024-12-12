# Note: this schema should be kept in sync with the parameters in constants.py, with the exception that not all of the parameters in DEFAULT_USER_PARAMETERS need to be present, as some are not directly set by the user.

mpcgwas_shared_parameters_properties = {
    "NUM_SNPS": {"type": "integer", "minimum": 1, "maximum": 1_000_000_000},
    "NUM_COVS": {"type": "integer", "minimum": 1, "maximum": 1000},
    "NUM_DIM_TO_REMOVE": {"type": "integer", "minimum": 1, "maximum": 100},
    "SKIP_QC": {"type": "integer", "minimum": 0, "maximum": 1},
    "IMISS_UB": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "HET_LB": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "HET_UB": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "GMISS_UB": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "MAF_LB": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "MAF_UB": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "HWE_UB": {"type": "number", "minimum": 0.0, "maximum": 100.0},
    "LD_DIST_THRES": {"type": "integer", "minimum": 1, "maximum": 1_000_000_000},
}
mpcgwas_advanced_parameters_properties = {
    "ITER_PER_EVAL": {"type": "integer", "minimum": 1, "maximum": 100},
    "NUM_OVERSAMPLE": {"type": "integer", "minimum": 0, "maximum": 100},
    "NUM_POWER_ITER": {"type": "integer", "minimum": 0, "maximum": 100},
    "NBIT_K": {"type": "integer", "minimum": 1, "maximum": 1000},
    "NBIT_F": {"type": "integer", "minimum": 1, "maximum": 1000},
    "NBIT_V": {"type": "integer", "minimum": 1, "maximum": 1000},
    "BASE_P": {"type": "string", "pattern": "^[0-9]{1,999}$"},
}

pca_shared_parameters_properties = {
    "num_columns": {"type": "integer", "minimum": 1, "maximum": 1_000_000_000},
    "num_pcs_to_remove": {"type": "integer", "minimum": 0, "maximum": 100},
}
pca_advanced_parameters_properties = {
    "iter_per_eigenval": {"type": "integer", "minimum": 0, "maximum": 100},
    "num_oversampling": {"type": "integer", "minimum": 0, "maximum": 100},
    "num_power_iters": {"type": "integer", "minimum": 0, "maximum": 100},
    "mpc_field_size": {"type": "integer", "minimum": 1, "maximum": 1000},
    "mpc_data_bits": {"type": "integer", "minimum": 1, "maximum": 1000},
    "mpc_frac_bits": {"type": "integer", "minimum": 1, "maximum": 1000},
}

sfgwas_shared_parameters_properties = {
    "num_snps": {"type": "integer", "minimum": 1, "maximum": 1_000_000_000},
    "num_covs": {"type": "integer", "minimum": 1, "maximum": 1000},
    "num_pcs_to_remove": {"type": "integer", "minimum": 0, "maximum": 100},
    "skip_qc": {"type": "string", "enum": ["false", "true"]},
    "imiss_ub": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "het_lb": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "het_ub": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "gmiss": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "maf_lb": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "hwe_ub": {"type": "number", "minimum": 0.0, "maximum": 100.0},
    "snp_dist_thres": {"type": "integer", "minimum": 0, "maximum": 1_000_000_000},
}
sfgwas_advanced_parameters_properties = {
    "iter_per_eigenval": {"type": "integer", "minimum": 0, "maximum": 100},
    "num_oversampling": {"type": "integer", "minimum": 0, "maximum": 100},
    "num_power_iters": {"type": "integer", "minimum": 0, "maximum": 100},
    "mpc_field_size": {"type": "integer", "minimum": 1, "maximum": 1000},
    "mpc_data_bits": {"type": "integer", "minimum": 1, "maximum": 1000},
    "mpc_frac_bits": {"type": "integer", "minimum": 1, "maximum": 1000},
}

# sfrelate_shared_parameters_properties = {}
sfrelate_advanced_parameters_properties = {
    "PARA": {"type": "number", "minimum": 1, "maximum": 100},
    "ENCLEN": {"type": "integer", "minimum": 1, "maximum": 1000},
    "SEGLEN": {"type": "number", "minimum": 0.0, "maximum": 100.0},
    "STEPLEN": {"type": "number", "minimum": 0.0, "maximum": 100.0},
    "K": {"type": "integer", "minimum": 1, "maximum": 1000},
    "L": {"type": "integer", "minimum": 1, "maximum": 1000},
    "MAXL": {"type": "integer", "minimum": 1, "maximum": 1000},
    "s": {"type": "number", "minimum": 0.0, "maximum": 1.0},
}

secure_dti_shared_parameters_properties = {
    "FEATURE_RANK": {"type": "integer", "minimum": 1, "maximum": 1_000_000_000},
    "FEATURES_FILE": {"type": "string", "pattern": "^$|^[a-z0-9][a-z0-9._-]{2,62}/.+$"},
    "LABELS_FILE": {"type": "string", "pattern": "^$|^[a-z0-9][a-z0-9._-]{2,62}/.+$"},
    "TRAIN_SUFFIXES": {"type": "string", "pattern": "^$|^[a-z0-9][a-z0-9._-]{2,62}/.+$"},
    "TEST_SUFFIXES": {"type": "string", "pattern": "^$|^[a-z0-9][a-z0-9._-]{2,62}/.+$"},
}

secure_dti_advanced_parameters_properties = {
    "NBIT_K": {"type": "integer", "minimum": 1, "maximum": 1000},
    "NBIT_F": {"type": "integer", "minimum": 1, "maximum": 1000},
    "NBIT_V": {"type": "integer", "minimum": 1, "maximum": 1000},
    "BASE_P": {"type": "string", "pattern": "^[0-9]{1,999}$"},
}

default_user_parameters_properties = {
    # "PUBLIC_KEY":
    "GCP_PROJECT": {"type": "string", "pattern": "^$|^[a-z]([a-z0-9-]{4,28}[a-z0-9])?$"},
    "DATA_PATH": {"type": "string", "pattern": "^$|^([a-zA-Z0-9_.-]+/)*([a-zA-Z0-9_.-]+)$", "maxLength": 1000},
    # "GENO_BINARY_FILE_PREFIX":
    # NUM_INDS<UUID> (see patternProperties below)
    # "NUM_THREADS":
    "NUM_CPUS": {"type": "integer", "minimum": 1, "maximum": 1_000},
    # "ZONE":
    "BOOT_DISK_SIZE": {"type": "integer", "minimum": 10, "maximum": 10_000},
    # "DATA_HASH":
    # "IP_ADDRESS":
    # "PORTS":
    # "AUTH_KEY":
    "SEND_RESULTS": {"type": "string", "enum": ["Yes", "No"]},
    "RESULTS_PATH": {"type": "string", "pattern": "^$|^[a-z0-9][a-z0-9._-]{2,62}/.+$"},
    "CREATE_VM": {"type": "string", "enum": ["Yes", "No"]},
    "DELETE_VM": {"type": "string", "enum": ["Yes", "No"]},
}

parameters_schema = {
    "type": "object",
    "properties": {
        **mpcgwas_shared_parameters_properties,
        **mpcgwas_advanced_parameters_properties,
        **pca_shared_parameters_properties,
        **pca_advanced_parameters_properties,
        **sfgwas_shared_parameters_properties,
        **sfgwas_advanced_parameters_properties,
        # **sfrelate_shared_parameters_properties,
        **sfrelate_advanced_parameters_properties,
        **secure_dti_shared_parameters_properties,
        **secure_dti_advanced_parameters_properties,
        **default_user_parameters_properties,
    },
    "patternProperties": {
        "^NUM_INDS[\\w-]{,64}$": {
            "type": "integer",
            "minimum": 1,
            "maximum": 1_000_000_000,
        }
    },
    "additionalProperties": False,
}
