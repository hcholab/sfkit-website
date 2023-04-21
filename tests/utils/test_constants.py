from src.utils.constants import SERVER_GCP_PROJECT, default_user_parameters


def test_default_user_parameters():
    # Test for non-demo mode
    result = default_user_parameters("MPC-GWAS")
    assert result["GCP_PROJECT"]["value"] != SERVER_GCP_PROJECT
    assert result["NUM_INDS"]["value"] != "1000"
    assert result["PORTS"]["value"] == "null,8060,8080"

    # Test for demo mode with study_type = "MPC-GWAS"
    result = default_user_parameters("MPC-GWAS", demo=True)
    assert result["GCP_PROJECT"]["value"] == SERVER_GCP_PROJECT
    assert result["NUM_INDS"]["value"] == "1000"
    assert result["PORTS"]["value"] == "null,8060,8080"

    # Test for demo mode with study_type = "PCA"
    result = default_user_parameters("PCA", demo=True)
    assert result["GCP_PROJECT"]["value"] == SERVER_GCP_PROJECT
    assert result["NUM_INDS"]["value"] == "2504"
    assert result["PORTS"]["value"] == "null,8060,8080"

    # Test for demo mode with study_type = "SF-GWAS"
    result = default_user_parameters("SF-GWAS", demo=True)
    assert result["GCP_PROJECT"]["value"] == SERVER_GCP_PROJECT
    assert result["NUM_INDS"]["value"] == "2000"
    assert result["PORTS"]["value"] == "null,8060,8080"

    # Test for some other study_type
    result = default_user_parameters("some-other-study-type", demo=True)
    assert result["GCP_PROJECT"]["value"] == SERVER_GCP_PROJECT
    assert result["PORTS"]["value"] == "null,8060,8080"
