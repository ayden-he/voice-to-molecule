from rdkit import Chem


def test_rdkit_builds_ethanol():
    # SMILES describes ethanol as two carbons followed by an oxygen.
    molecule = Chem.MolFromSmiles("CCO")

    assert molecule is not None
    assert molecule.GetNumAtoms() == 3
    assert Chem.MolToSmiles(molecule) == "CCO"
