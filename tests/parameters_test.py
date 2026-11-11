import pytest
from jsonschema import ValidationError, validate

from src.utils.schemas.parameters import parameters_schema


@pytest.mark.parametrize("value", ["0.01,0.001", "0.5", "0.50", ".05", "0.1", "0.45,0.0001", "0.000025"])
def test_global_max_maf_accepted(value):
    validate(instance={"global_max_maf": value}, schema=parameters_schema)


# secure-rvas accepts thresholds above 0 and at most 0.5
@pytest.mark.parametrize("value", ["", "0", "0.0", "0.51", "0.500001", "1", "1.0", "0.01, 0.001", "0.01,", "1e-3", "rare"])
def test_global_max_maf_rejected(value):
    with pytest.raises(ValidationError):
        validate(instance={"global_max_maf": value}, schema=parameters_schema)
