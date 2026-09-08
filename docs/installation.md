# Installation

boamotion needs **Python 3.10 or newer**. Everything else it depends on — numpy, tifffile,
pandas, matplotlib and pyyaml — is installed with it.

## With pip

```bash
pip install git+https://github.com/quasar1357/boamotion.git
```

## From a clone

```bash
git clone https://github.com/quasar1357/boamotion.git
cd boamotion
pip install .
```

Add `-e ".[dev]"` instead of `.` to install it in editable mode together with the test
tools, which is what you want if you intend to change the code.

## With conda

The repository ships an environment file, which creates the environment and installs
boamotion into it in one step:

```bash
conda env create -f environment.yml
conda activate boamotion
```

## Check that it worked

```bash
python -c "import boamotion; print(boamotion.__version__)"
```

To run the [demo](demo.ipynb) notebook you also need Jupyter and a kernel for the
environment; the conda environment above already carries `ipykernel`.

```bash
pip install jupyterlab
jupyter lab
```
