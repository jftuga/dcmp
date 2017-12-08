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

**Usage**

```
    usage: dcmp.exe [-h] [--recurse] [--threads THREADS] [--exact] [--ignoredate]
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

**Example**

```
    c:\> dcmp.exe -d -T8 -e --stats -r r:\a r:\b

    The '*' denotes a newer or larger file
    
    ----------------------------------------------------------------------------------
    | 1) r:\a\linux-4.14\fs\ext4                                                     |
    | 2) r:\b\linux-4.14\fs\ext4                                                     |
    +--------+-----------+--------+--------+--------+-------------------+------------+
    |  fname | same meta | size-1 | size-2 | date-1 |            date-2 | exact data |
    +--------+-----------+--------+--------+--------+-------------------+------------+
    |  dos.h | Only in 2 |        |      0 |        | 12/06/17 14:41:29 |            |
    | dos1.c | Only in 2 |        |  2,491 |        | 12/06/17 14:41:16 |            |
    | dos2.c | Only in 2 |        |  2,538 |        | 12/06/17 14:41:18 |            |
    | dos3.c | Only in 2 |        |  2,585 |        | 12/06/17 14:41:23 |            |
    +--------+-----------+--------+--------+--------+-------------------+------------+
    
    --------------------------------------------------------------------------------------------------
    | 1) r:\a\linux-4.14\ipc                                                                         |
    | 2) r:\b\linux-4.14\ipc                                                                         |
    +-----------+-----------+--------+--------+-------------------+---------------------+------------+
    |     fname | same meta | size-1 | size-2 |            date-1 |              date-2 | exact data |
    +-----------+-----------+--------+--------+-------------------+---------------------+------------+
    |     sem.c |     False | 59,442 | 59,442 | 08/18/17 16:31:55 | * 11/12/17 13:46:13 |       True |
    |     shm.c |     False | 39,497 | 39,497 | 08/18/17 16:31:55 | * 11/12/17 13:46:13 |       True |
    | syscall.c |     False |  4,430 |  4,430 | 08/18/17 16:31:55 | * 11/12/17 13:46:13 |       True |
    +-----------+-----------+--------+--------+-------------------+---------------------+------------+
    
    -------------------------------------------------------------------------------------------------
    | 1) r:\a\linux-4.14\mm                                                                         |
    | 2) r:\b\linux-4.14\mm                                                                         |
    +----------+-----------+--------+--------+-------------------+---------------------+------------+
    |    fname | same meta | size-1 | size-2 |            date-1 |              date-2 | exact data |
    +----------+-----------+--------+--------+-------------------+---------------------+------------+
    | z3fold.c |     False | 29,955 | 29,955 | 11/12/17 13:46:13 | * 11/18/17 01:50:58 |      False |
    +----------+-----------+--------+--------+-------------------+---------------------+------------+
    
    ---------------------------------------------------------------------------------------------------
    | 1) r:\a\linux-4.14\net\wimax                                                                    |
    | 2) r:\b\linux-4.14\net\wimax                                                                    |
    +----------+-----------+----------+--------+---------------------+-------------------+------------+
    |    fname | same meta |   size-1 | size-2 |              date-1 |            date-2 | exact data |
    +----------+-----------+----------+--------+---------------------+-------------------+------------+
    | op-msg.c |     False | * 12,012 | 12,008 | * 12/07/17 19:19:19 | 11/12/17 13:46:13 |      False |
    +----------+-----------+----------+--------+---------------------+-------------------+------------+
    
    -------------------------------------------------------------------------------------
    | 1) r:\a\linux-4.14\sound\sparc                                                    |
    | 2) r:\b\linux-4.14\sound\sparc                                                    |
    +-----------+-----------+--------+--------+-------------------+--------+------------+
    |     fname | same meta | size-1 | size-2 |            date-1 | date-2 | exact data |
    +-----------+-----------+--------+--------+-------------------+--------+------------+
    | sparkle.c | Only in 1 |    641 |        | 12/07/17 10:54:39 |        |            |
    | sparkle.h | Only in 1 |    980 |        | 12/07/17 10:54:52 |        |            |
    +-----------+-----------+--------+--------+-------------------+--------+------------+

    --------------------------------------------------------------------------------------
    | dcmp -d -T8 -e --stats -r r:\a r:\b                                                |
    | runtime (h:m:s) 00:00:4.02                                                         |
    +-----------+---------------+------------+----------------+--------------------------+
    | same_meta | not_same_meta | exact_data | not_exact_data | same_meta_different_data |
    +-----------+---------------+------------+----------------+--------------------------+
    | 0         | 5             | 3          | 2              | 0                        |
    +-----------+---------------+------------+----------------+--------------------------+
```
