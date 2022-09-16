# Instructions for building the Python venv

## Description
Because we don't wnt to install Python modules on F5, we need to create a Virtual Environment that uses **Python 2.7** (this is the Python version included on F5) and the **oci** module.

Virtual Environment will be created on local machine running Linux or MacOS, then it can be uploaded to the F5.

## Install PIP in your local build environment:
* For Oracle Linux:
    * sudo yum install python-pip
* For MacOS:
    * sudo easy_install pip
* For Debian/Ubuntu Linux:
    * sudo apt-get install python-pip

* Once PIP is installed, use pip to install virtualenv
    * pip install virtualenv

### Create Python virtual environment:
```
virtualenv -p python2 venv
source venv/bin/activate
pip install oci
pip install requests
pip install multiprocessing
pip install datetime
```

Included **run-script.sh** will be used as a BASH script to change the python source to the one used by the Virtual Environment.