
IGM: An Integrated Genome Modeling Platform
=====================================
This is the modeling platform used in Frank U. Alber lab, University of California Los Angeles.
A population of individual full genome (diploid) structures is generated, which fully recapitulates a variety of experimental genomic and/or imaging data. It does NOT preprocess raw data.

May 2020

-  Hi-C data, SPRITE data
-  excluded volume, imaging data for volumetric restraints (e.g., both nuclear envelope and nuclear bodies)
-  lamina DamID data in combination with ellipsoidal nuclear envelope
-  FISH data, both "pairs" and "radial" options active (a code is available to interpolated data if the number of points in the availablr distribution is smaller than the number of structures we would like to simulate)
- experimental volume maps are included, with approximate radial force field

Repository organization
-----------------------
- ``` igm ```: full IGM code(s)
- ``` bin ```: IGM run, server and GUI scripts. In particular, refer to ```igm-run.sh``` (actual submission script) and ```igm-report.sh``` (post-processing automated script)
- ``` test ```: example inputs for preliminary test runs
- ``` HCP_scripts ```: create ipyparallel environment and submit igm run on a SGE scheduler based HCP resource


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
    conda install pandas swig cython cgal==4.14 hdf5 h5py numpy scipy matplotlib \
                  tornado ipyparallel cloudpickle
    ```
    -   It looks like ```cgal``` version needs to be 4.14, there are some compatibility issues with latest 5.0 version.
    
    If you _really_ do not want to use conda, most of the packages can be 
    installed with pip, but it is up to you to download and build cgal and 
    hdf5, and eventually set the correct include/library paths during 
    installation.

-   Install alabtools (github.com/alberlab/alabtools)
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
    echo "[DEFAULT]" > ${HOME}/.igm/user_defaults.cfg
    echo "optimization/kernel_opts/lammps/lammps_executable = "$(pwd)/src/lmp_serial >> ${HOME}/.igm/user_defaults.cfg
    ```

Installation on MacOS
--------------
-   Installation on MacOS poses additional challenges, especially on 11.14 Mojave (updated Sept 2019).  ```gcc``` compiler may not be pre-installed; instead, the more efficient ```clang``` might be (this can be checked with ```gcc --version```):

    ``` 
    $ which gcc
    /usr/bin/gcc
    $ gcc --version
    Configured with: --prefix=/Applications/Xcode.app/Contents/Developer/usr --with-gxx-include-dir=/usr/include/c++/4.2.1
    Apple LLVM version 7.3.0 (clang-703.0.29)
    Target: x86_64-apple-darwin15.4.0
    Thread model: posix
    InstalledDir: /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin
    ```

If you are getting this printout, then there is NO actual gcc installed. In order to circumvent that, the following procedure worked for me:

-   First install ```gcc``` using ```Homebrew```: 
    ``` brew install gcc```

    A gcc compiler will be installed, but we still need to make sure it supercedes the default ```clang```, anytime the C compiler is called. Assume the 9.0 version was installed, then the default installation path reads ```/usr/local/Cellar/gcc/9.0.2/```

-   Make sure the default gcc compiler points to that folder, i.e.

    ``` 
    export CXX=/usr/local/Cellar/gcc/9.0.2/gcc+-9
    export CC=/usr/local/Cellar/gcc/9.0.2/gcc-9
    ```

-   Then, ```alabtools``` can be installed in the regular way



Quickstart
----------
IGM has a web-based ui, which is probably the quickest way to setup and perform a IGM run. After installing igm,
create a new directory, register it as IGM directory, and start a server

```
mkdir igm_test
cd igm_test
igm-register-dir
igm-server
```  

You shoud see something like this:

```
##### Securing server #####
Reading secure tokens from /home/polles/.igm/server-cfg.json

######################
##### IGM Server #####
######################

The way to connect to the server depends on your platform.
The list of ips for this machine is: 
 ['xxx.xxx.xxx.xxx', '192.168.0.17'] 

If the machine running igm-server is accessible from your workstation, my educated guess is to try to copy and paste the 
following address in your browser:
      192.168.0.17:43254?q=f50e03667b184cd0b98d684fbc66419e
If the machine is not accessible from your workstation you may need to set up a tunnel (with --tunnel option) to a node 
which is accessible from your workstation (for example a login node)

The secure token for this session is: f50e03667b184cd0b98d684fbc66419e
##### IGM server starting #####

```

There are details to take into consideration here. If you are running locally, it should be sufficient to point your
browser to the address provided. If you are running on a cluster, you need to obtain access to that machine and port
from your local machine.

`igm-server` can also try to estabilish a ssh tunnel with a remote machine as endpoint using the --tunnel option.
See `igm-server --help` for all the options.

The first thing to set up in order to perform a run is a configuration file, in json format. The amount of options is 
pretty massive, but to make it easier, it can be created from the UI. Most of the defaults are usually okay. For people
allergic to UIs, the schema is described in a file included in IGM, its location can be found out using:

```python -c "import igm; print(igm.__file__.replace('__init__.py', '') + 'core/defaults/config_schema.json')"```

Use on clusters
---------------
You can actually run a simulation on a local machine but, I mean, do you really want to? Anyway, the code should work 
with three different kind of parallel schedulers. The first is a basic serial, for testing very quick runs. Then there
are *dask* and *ipyparallel*. Ipyparallel is widely tested, for dask it may work. Also there is  a SLURM controller, but
it may hurt your performance, so the other options are probably better. 

The main idea is that, whatever is your undelying platform, you should first start a ipyparallel or dask cluster there,
with a scheduler and workers running. Once that is up, you can run igm either from the UI or the command line.
The command `igm-run` can be called from the igm directory and takes the configuration json as the only argument.

`igm-run igm-config.json`

Important notes
---------------
-   IGM uses works mostly through the file system. The reason for the design stood on the local cluster details, persistence
    of data, and minimization of memory required by the scheduler and workers. That means, in short, that scheduler, workers 
    and the node which executes the igm-run script *need to have access to a shared filesystem where all the files will be 
    located*.
-   Preprocessing of data is a big deal itself. Hi-C matrices need to be transformed to probability matrices, DamID 
    profiles too, FISH and SPRITE data needs to be preprocessed and transformed to the correct format. Some of these
    processes have yet to be completely and exaustively documented publicly. We are working on it, but in the meantime
    email if you need help.
  
Test
----
-   Enter the ```test``` folder: data and scripts for a 2Mb IGM calculation with Hi-C restraints are provided;
    -   ```.hcs``` file is a 2Mb resolution Hi-C contact map
    - ``` config_file.json ``` is the .json configuration file with all the parameters needed for the calculation.
-   Edit the path entries to the lammps executable file (and all paths, if needed)
-   ```igm-run config_file.json >> output.txt```


