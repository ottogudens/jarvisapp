from backend.perfiles_default import PERFILES_DEFAULT


def test_automotive_engineer_profile_is_seeded_with_safety_and_vin_rules():
    profile = next(item for item in PERFILES_DEFAULT if item["nombre"] == "Ingeniero Automotriz")

    instructions = profile["instrucciones_base"]
    assert "VIN" in instructions
    assert "DTC/OBD-II" in instructions
    assert "Seguridad no negociable" in instructions
    assert "nunca inventes números OEM" in instructions
