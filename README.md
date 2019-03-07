# igm

A Integrated Genome Modeling Platform
=====================================

This is the modeling platform used in Frank U. Alber lab.
It automates most of the modeling effort. It does not preprocess raw data.

Dependencies
------------
IGM not longer supports python 2, so you'll need a python3 environment. 
The package depends on a number of other libraries, most of them publicly 
available on pip. In addition, some other packages are required: 

- alabtools (github.com/alberlab/alabtools)
- a modified version of LAMMPS (github.com/alberlab/lammpgen)

Installation on linux
---------------------
-   Many of the alabtools and IGM dependencies can be installed with a
    few commands if you are using conda 
    (https://www.anaconda.com/distribution/)
    ```
    # optional - create a new environment for igm
    conda create -n igm python=3.6
    source activate igm
    # install dependencies
    conda install pandas swig cython cgal hdf5 h5py numpy scipy matplotlib \
                  tornado ipyparallel cloudpickle
    ```
    If you _really_ do not want to use conda, most of the packages can be 
    installed with pip, but it is up to you to download and build cgal and 
    hdf5, and eventually set the correct include/library paths during 
    installation.

-   Install alabtools (github.com/alberlab/alabtools).
    ```
    pip install git+https://github.com/alberlab/alabtools.git
    ```
    Note: on windows, conda CGAL generates the library, but the name depends 
    on the build, e.g CGAL-vc140-mt-4.12.lib. Go to 
    <environment directory>/Library/lib/ and copy the CGAL library to CGAL.lib
    before pip installing alabtools.
        
-   Install IGM
    ```
    pip install git+https://github.com/alberlab/igm.git 
    ```
    
-   Download and build a serial binary of the modified LAMMPS version
    ```
    git clone https://github.com/alberlab/lammpgen.git
    cd lammpgen/src
    make yes-user-genome
    make yes-molecule
    make serial
    # create a user defaults file with the path of the executable
    mkdir -p ${HOME}/.igm
    echo "optimization/kernel_opts/lammps/lammps_executable = "$(pwd)/src/lmp_serial >> ${HOME}/.igm/user_defaults.cfg
    ```
    
