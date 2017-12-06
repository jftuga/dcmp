# dcmp
Compare files within two directory trees for equivalency.

The purpose of this program is to recursively examine two directories to find all files that are either the 
same, different, or mutually exclusive.  

Two files are considered to be the equivalent if they have the same:

* Name
* Size
* Modification Time (this check can be excluded with **--ignoredate**)

Only metadata is compared.  File contents are not compared unless **--exact** is invoked.
When this option is used, you may want to also invoke the **--threads** option to speed up processing.

Groups of files and directories can be excluded with regular expressions via the **--exfile** and **--exdir** options.

This was written in **Python 3.6** and has been tested on Windows 10 and MacOS Sierra.

A Windows executable can be created with [PyInstaller 3.3](http://www.pyinstaller.org/):
```
    : ensure both dcmp.py and veryprettytablepatched.py are in the current directory
    pyinstaller -F --noupx dcmp.py
```

All command line options can be reviewed by invoking **-h**:

```
    usage: dcmp.py [-h] [--recurse] [--threads THREADS] [--exact] [--ignoredate]
                   [--exdir EXDIR] [--exfile EXFILE]
                   [--diff | --same | --xor | --one | --two | --version]
                   [--pgm PGM] [--html] [--stats] [--verbose]
                   dname1 dname2
    
    Directory Compare: compare files within two directory trees for equivalency
    
    optional arguments:
      -h, --help            show this help message and exit
      --diff, -d            only show files that are different
      --same, -s            only show files that are the same
      --xor, -x             only show files residing in one directory or the
                            other; but not both
      --one, -1             only show files in dname1
      --two, -2             only show files in dname2
      --version             show program's version number and exit
    
    Positional Arguments:
      These arguments come after any flags and in the order they are listed here
      and are required.
    
      dname1                first directory to compare
      dname2                second directory to compare
    
    Operational:
      --recurse, -r         recusively traverse all subdirectories
      --threads THREADS, -T THREADS
                            use this number of threads
      --exact, -e           compare file contents as well as metadata
      --ignoredate, -id     do not compare file time stamps, good to use with -e
      --exdir EXDIR         a ; delimited list of regular expressions to exclude,
                            only applied to directory names
      --exfile EXFILE       a ; delimited list of regular expressions to exclude,
                            only applied to file names
    
    Output Arguments:
      --pgm PGM             output diff commands, by using PGM as your comparision
                            program
      --html                create HTML output
      --stats, -S           print run time & statistical totals to STDERR
      --verbose, -v         output exclusions to STDERR
```
