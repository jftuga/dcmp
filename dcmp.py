#!/usr/bin/env python3

# dcmp.py - Directory Compare
# -John Taylor
# Nov-13-2017

# Compare files within two directory trees for equivalency

# MIT License; Copyright (c) 2017 John Taylor
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import argparse
import io
import multiprocessing
from multiprocessing.managers import BaseManager, DictProxy
import os
import queue
import re
import sys
import time
import concurrent.futures
from collections import defaultdict
# adapted from https://raw.githubusercontent.com/andrewspiers/VeryPrettyTable/master/veryprettytable.py
from veryprettytablepatched import VeryPrettyTablePatched

#############################################################################

class MyManager(BaseManager):
    """Create a  multiprocessing-safe defaultdict
    https://stackoverflow.com/questions/9256687/using-defaultdict-with-multiprocessing
    """
    pass

#############################################################################

class Dir_Compare():
    """Compare files within two directory trees for equivalency
    """

    class_version = "1.13"

    # output date format
    date_time_fmt = "%m/%d/%y %H:%M:%S"
    # buffer size used to compare, when --exact is used
    file_cmp_bufsize = io.DEFAULT_BUFFER_SIZE
    # when processing the current directory, maintain a queue of subdirectories to be processed
    dir_queue = None
    # a list of directories to be skipped via the --exdir option
    skip_directories = []
    # a list of files to be skipped via the --exfile option
    skip_files = []
    # automatically built from the skip_directories list
    re_skip_directories = []
    # automatically built from the skip_files list
    re_skip_files = []
    # number of threads to use, controlled by --threads
    max_workers = 1
    # a list of 2-length tuples which contain matching directory names
    all_twins = []
    # when --stats is used, collect accumulation stats such as the total number of same files, diff files, etc.
    mgr = MyManager()
    file_stats = None  # this is redefined in __init__()

    # when --pgm is used, save the files that are different, via a list of tuples (similar to all_twins)
    output_files = []
    # when --stats is used, keep track of program run time
    time_start = 0
    time_end = 0

    def __init__(self, *args, **kwargs):
        """ No argurments need to be passed in.
            Process cmd line arguments and start comparing directories
        """
        self.dir_queue = queue.Queue()
        self.process_cmd_line_args()

        if self.args.stats:
            self.time_start = time.time()

        # create a list of reg expr that will be used to skip directories
        if self.args.exdir:
            self.skip_directories += self.args.exdir.split(";")
            for regexpr in self.skip_directories:
                try:
                    self.re_skip_directories.append( re.compile(regexpr,re.I))
                except:
                    print("Invalid directory regular expression: %s" % (regexpr))
                    sys.exit(141)

        # create a list of reg expr that will be used to skip files
        if self.args.exfile:
            self.skip_files += self.args.exfile.split(";")
            for regexpr in self.skip_files:
                try:
                    self.re_skip_files.append( re.compile(regexpr,re.I))
                except:
                    print("Invalid file regular expression: %s" % (regexpr))
                    sys.exit(142)

        output = self.output_to_html if self.args.html else self.output_to_screen

        if self.args.threads:
            self.max_workers = int(self.args.threads)
            if self.max_workers <= 0:
                print("\nError: threads must be greater than zero\n");
                sys.exit(1)
            self.mgr.start()
            self.file_stats = self.mgr.defaultdict(int)
        else:
            self.file_stats = defaultdict(int)

        if not self.args.html:
            print()
            print("The '*' denotes a newer or larger file")
            print()
        else:
            print()
            print("<h3>The '*' denotes a newer or larger file</h3><br />")
            print()

        # process the 2 directories given on the cmd line
        tbl, dir1, dir2 = self.dir_cmp(self.args.dname1, self.args.dname2)
        output(tbl, self.args.dname1, self.args.dname2)

        # process and child subdirectories in single-process mode
        if self.args.recurse and not self.args.threads:
            while not self.dir_queue.empty():
                twins = self.dir_queue.get()
                tbl, dir1, dir2 = self.dir_cmp(*twins)
                output(tbl, *twins)

        # process and child subdirectories in multi-process mode
        # a list of all subdirectories must be created first (in one thread),
        # which is not the case for single-process mode (above)
        elif self.args.recurse and self.args.threads:
            self.find_all_twins(self.args.dname1, self.args.dname2)

            with concurrent.futures.ProcessPoolExecutor(self.max_workers) as executor:
                result = {executor.submit(self.dir_cmp, *twins): twins for twins in self.all_twins}
                for future in concurrent.futures.as_completed(result):
                    if future.done():
                        output(*future.result())
                
        if self.args.stats:
            self.time_end = time.time()
            x = VeryPrettyTablePatched()
            x.field_names = ( "same_meta", "not_same_meta", "exact_data", "not_exact_data", "same_meta_different_data" )
            x.align = "l"
            x.add_row((self.file_stats["same_meta"], self.file_stats["not_same_meta"], self.file_stats["exact_data"], self.file_stats["not_exact_data"], self.file_stats["same_meta_different_data"]))
            if not self.args.html:
                self.output_stats(x)
            else:
                self.output_stats_to_html(x)

    #############################################################################

    def process_cmd_line_args(self):
        """Each cmd line arguments is referenced by self.args.xxx, where xxx is
           the first option to add_argument(), example: recurse => self.args.recurse 
        """

        parser = argparse.ArgumentParser(description="Directory Compare: compare files within two directory trees for equivalency")
        positional = parser.add_argument_group(title="Positional Arguments", description="These arguments come after any flags and in the order they are listed here and are required.")
        positional.add_argument("dname1", metavar="dname1",    help="first directory to compare")
        positional.add_argument("dname2", metavar="dname2",    help="second directory to compare")

        operational_opts = parser.add_argument_group(title="Operational", description=None)
        operational_opts.add_argument("--recurse", "-r", action="store_true", help="recusively traverse all subdirectories")
        operational_opts.add_argument("--threads", "-T", action=None, help="use this number of threads")
        operational_opts.add_argument("--exact", "-e", action="store_true", help="compare file contents as well as metadata")
        operational_opts.add_argument("--ignoredate", "-id", action="store_true", help="do not compare file time stamps, good to use with -e")
        operational_opts.add_argument("--exdot", action="store_true", help="ignore both files and directories that begin with a dot")
        operational_opts.add_argument("--exdir", action=None, help="a ; delimited list of regular expressions to exclude, only applied to directory names")
        operational_opts.add_argument("--exfile", action=None, help="a ; delimited list of regular expressions to exclude, only applied to file names")

        mutuallyexclusive_opts = parser.add_mutually_exclusive_group()
        mutuallyexclusive_opts.add_argument("--diff", "-d", action="store_true", help="only show files that are different")
        mutuallyexclusive_opts.add_argument("--same", "-s", action="store_true", help="only show files that are the same")
        mutuallyexclusive_opts.add_argument("--xor", "-x", action="store_true", help="only show files residing in one directory or the other; but not both")
        mutuallyexclusive_opts.add_argument("--one", "-1", action="store_true", help="only show files in dname1")
        mutuallyexclusive_opts.add_argument("--two", "-2", action="store_true", help="only show files in dname2")
        mutuallyexclusive_opts.add_argument('--version', action='version', version='version %s' % (self.class_version))

        output_opts = parser.add_argument_group(title="Output Arguments",description=None)
        output_opts.add_argument("--pgm", action=None, help="output diff commands, by using PGM as your comparision program, must be used with -e")
        output_opts.add_argument("--html", action="store_true", help="create HTML output which should then be redirected to a file")
        output_opts.add_argument("--stats", "-S", action="store_true", help="print run time & statistical totals to STDERR")
        output_opts.add_argument("--verbose", "-v", action="store_true", help="output exclusions to STDERR")

        self.args = parser.parse_args()

    #############################################################################

    def file_cmp_exact(self, fname1:str, fname2:str) -> bool:
        """Compare two files, byte for byte

            Args:
                fname1: the first file to compare

                fname2: the second file to compare

            Returns:
                True if the 2 files contain exactly the same data, False otherwise
        """

        with open(fname1, 'rb') as fp1, open(fname2, 'rb') as fp2:
            while True:
                b1 = fp1.read(self.file_cmp_bufsize)
                b2 = fp2.read(self.file_cmp_bufsize)
                if b1 != b2:
                    return False
                if not b1:
                    return True
                
    #############################################################################

    def should_add_row(self,same_meta:bool,same_data:bool,are_both_dirs:bool) -> bool:
        """Determines when a row should be added to a VeryPrettyTablePatched object.

            Args:
                same_meta: True when the 2 files be compared have the same meta data

                same_data: True when the 2 files be compared have the same actual data

            Returns:
                True or False
        """
        
        if not self.args.diff and not self.args.same:
            return True

        if self.args.same and not self.args.exact and same_meta:
            return True

        if self.args.same and self.args.exact and same_meta and same_data:
            return True

        if self.args.diff and not self.args.exact and not same_meta:
            return True

        if self.args.diff and self.args.exact and not same_data:
            if are_both_dirs:
                return False
            return True

        if self.args.diff and self.args.exact and not same_meta:
            return True

        return False

    #############################################################################

    def find_all_twins(self, dname1:str, dname2:str):
        """Given 2 directories, append to the self.all_twins list, a tuple
           of 'twin' subdirectories.  Ex: ("r:\\a\\bin\\test", "r:\\b\\bin\\test")

            Args:
                   dname1: the first directory to compare

                dname2: the second directory to compare

            Returns:
                Nothing, as self.all_twins is a class variable
        """

        gen_folder = lambda dname : set(f.name for f in os.scandir(dname) if f.is_dir() )
        same_dnames  = gen_folder(dname1) & gen_folder(dname2)
        same_dnames = sorted(same_dnames)

        for d in same_dnames:
            a = os.path.join(dname1,d)
            b = os.path.join(dname2,d)
            self.all_twins.append( (a,b) )
            self.find_all_twins(a,b)
            
    #############################################################################

    def dir_cmp(self, dname1:str, dname2:str) -> tuple:
        """Compare two directories for equivalency

        Args:
            dname1: the first directory to compare

            dname2: the second directory to compare

        Returns:
            Tuple containing: ( a VeryPrettyTablePatched object, dname1, dname2)
            dname1 and dname2 are needed when the -T option is used

        """
        x = VeryPrettyTablePatched()
        x.field_names = ( "fname", "same meta", "size-1", "size-2", "date-1", "date-2", "exact data")
        x.align = "r"

        if os.path.basename(dname1) in self.skip_directories: 
            return x

        if os.path.basename(dname2) in self.skip_directories: 
            return x

        performed_exact_file_cmp = {}

        d1 = {}
        d2 = {}

        ### start of nested functions
        #
        def _in_exclusion_list(fname:str, re_list:list) -> bool:
            """See if fname is excluded via the re_list
               fname can actually be a file name or directory name
            """
            for skip in re_list:
                match = skip.findall(fname)
                if match:
                    #print(fname,match)
                    return True

            return False

        def should_not_exclude(obj_name:str, is_file:bool, is_dir:bool):
            """Determine if a file or directory should be excluded via the 
               --exdot, --exdir and/or --exfile options
            """
            if self.args.exdot and "." == obj_name[0]:
                return False
            if is_file and self.args.exfile:
                file_should_skip = _in_exclusion_list(obj_name,self.re_skip_files)
                return not file_should_skip

            if is_dir and self.args.exdir:
                dir_should_skip = _in_exclusion_list(obj_name,self.re_skip_directories)
                return not dir_should_skip

            return True
        #
        ### end of nested functions

        for f in os.scandir(dname1):
            if should_not_exclude(f.name, f.is_file(), f.is_dir()):
                mtime = f.stat().st_mtime if not self.args.ignoredate else 0
                d1[f.name] = ( f.is_dir(), f.is_file(), f.is_symlink(), f.stat().st_mode, f.stat().st_size, mtime )
            elif self.args.verbose:
                print("Excluded %s: %s" % ("file" if f.is_file() else "directory", os.path.join(dname1,f.name)), file=sys.stderr)

        for f in os.scandir(dname2):
            if should_not_exclude(f.name, f.is_file(), f.is_dir()):
                mtime = f.stat().st_mtime if not self.args.ignoredate else 0
                d2[f.name] = ( f.is_dir(), f.is_file(), f.is_symlink(), f.stat().st_mode, f.stat().st_size, mtime )
            elif self.args.verbose:
                print("Excluded %s: %s" % ("file" if f.is_file() else "directory", os.path.join(dname2,f.name)), file=sys.stderr)

        s1 = set(d1)
        s2 = set(d2)
        same_fnames = s1.intersection(s2)
        d1_only = s1.difference(s2)
        d2_only = s2.difference(s1)

        ### start of nested function
        #
        def add_exclusive_file(exclusive:set, d:dict, meta_val:int):
            """Used when the -1 or -2 options are employed
               This adds a row to the VeryPrettyTablePatched object and populates
               the results for dates and file sizes
            """

            display_time = lambda s: (s,'') if meta_val == 1 else ('',s)
            same_meta = "Only in %s" % (meta_val)
            for fname in exclusive:
                fname_time = time.localtime(d[fname][5])
                fname_fulldate =  time.strftime(self.date_time_fmt,fname_time)
                file_sz = "{:,}".format(d[fname][4]) if not d[fname][0] else "<DIR>"
                x.add_row( (fname, same_meta) + display_time(file_sz) + display_time(fname_fulldate) + ('',) )
        #
        ### end of nested function

        if self.args.one:
            add_exclusive_file(d1_only,d1,1)
        elif self.args.two:
            add_exclusive_file(d2_only,d2,2)
        elif not self.args.same:
            add_exclusive_file(d1_only,d1,1)
            add_exclusive_file(d2_only,d2,2)

        for fname in same_fnames:
            if self.args.recurse and d1[fname][0] and d2[fname][0]:
                self.dir_queue.put( (os.path.join(dname1,fname),os.path.join(dname2,fname)) )
                continue

            if self.args.xor or self.args.one or self.args.two:
                continue

            same_meta = True
            same_data = False
            performed_exact_file_cmp[fname] = ""
            if not self.args.ignoredate:
                fname_time_1 = time.localtime(d1[fname][5])
                fname_fulldate_1 = time.strftime(self.date_time_fmt,fname_time_1)
                fname_time_2 = time.localtime(d2[fname][5])
                fname_fulldate_2 = time.strftime(self.date_time_fmt,fname_time_2)
            else:
                fname_fulldate_1 = ""
                fname_fulldate_2 = ""

            f1_sz = "{:,}".format(d1[fname][4])
            f2_sz = "{:,}".format(d2[fname][4])

            metadata_identical = (d1[fname] == d2[fname])
            
            if not metadata_identical:
                same_meta = False

                # add a * to the bigger file
                if d1[fname][4] < d2[fname][4]:
                    f2_sz = "* %s" % (f2_sz)
                elif d1[fname][4] > d2[fname][4]:
                    f1_sz = "* %s" % (f1_sz)

                # add a * to the newer date
                if not self.args.ignoredate:
                    if fname_time_1 < fname_time_2:
                        fname_fulldate_2 = "* %s" % (fname_fulldate_2)
                    elif fname_time_1 > fname_time_2:
                        fname_fulldate_1 = "* %s" % (fname_fulldate_1)

            # metadata is identical, so check file contents if --exact is used
            # fname is a directory when True==d1[fname][0]
            if self.args.exact and not d1[fname][0]:
                same_data = self.file_cmp_exact(os.path.join(dname1,fname), os.path.join(dname2,fname))
                performed_exact_file_cmp[fname] = same_data

            if d1[fname][0]: f1_sz = "<DIR>"
            if d2[fname][0]: f2_sz = "<DIR>"

            are_both_dirs = (d1[fname][0] and d2[fname][0])

            if self.should_add_row(same_meta,same_data,are_both_dirs):
                exact_data = performed_exact_file_cmp[fname]
                x.add_row((fname, same_meta, f1_sz, f2_sz, fname_fulldate_1, fname_fulldate_2, exact_data))
                if self.args.pgm:
                    self.output_files.append( ( os.path.join(dname1,fname), os.path.join(dname2,fname) ) )
                
                if self.args.stats and not are_both_dirs:
                    if same_meta and not exact_data:
                        self.file_stats["same_meta_different_data"] += 1
                    elif same_meta:
                        self.file_stats["same_meta"] +=1
                    else:
                        self.file_stats["not_same_meta"] +=1
                        
                    if exact_data:
                        self.file_stats["exact_data"] += 1
                    else:
                        self.file_stats["not_exact_data"] += 1
                    
        return (x, dname1, dname2)

    #############################################################################

    def safe_print(self, data:str, isError=False):
        """ safely output print statements to the screen without have to worry any about unicode exceptions

            Args:
                data: what to safely output

                isError: when True, output to stderr; otherwise output to stdout
        """
        dest = sys.stdout if not isError else sys.stderr
        # can also use 'replace' instead of 'ignore' for errors= parameter
        print( str(data).encode(sys.stdout.encoding, errors='ignore').decode(sys.stdout.encoding), file=dest )

    #############################################################################


    def output_to_screen(self, x:VeryPrettyTablePatched, dname1:str, dname2:str):
        """Display the VeryPrettyTablePatched table to the screen

        Args:
            x: the VeryPrettyTablePatched containing rows that need to be displayed

            dname1: the first directory, used in the table's title

            dname2: the second directory, used in the table's title
        """
        tbl = x.get_string(sortby="fname")
        if not len(x._rows):
            return # do not output when there are no rows
        width = 3*len(x._widths) + sum(x._widths) + 1

        print("-"* width)
        print("| 1) %s %s |" % (dname1," " * (width - len(dname1)-8)))
        print("| 2) %s %s |" % (dname2," " * (width - len(dname2)-8)))
        try:
            print(tbl)
        except:
            self.safe_print(tbl)
        print()

        if self.args.pgm and self.args.exact:
            diff_file_count = 0
            d = VeryPrettyTablePatched()
            d.field_names = ( "diff", )
            d.align = "l"
            d.vertical_char=" "

            q1=q2=q3=""
            quote_val = '"'
            if self.args.pgm.find(" ") > -1:
                q1=quote_val

            for entry in x:
                # file is in both directories
                # exact = False
                if not entry._rows[0][6] and not entry._rows[0][1]:
                    q2=q3=""
                    full_path1 = os.path.join(dname1,entry._rows[0][0])
                    if full_path1.find(" ") > -1:
                        q2 = quote_val
                    full_path2 = os.path.join(dname2,entry._rows[0][0])
                    if full_path2.find(" ") > -1:
                        q3 = quote_val
                    cmd = "%s%s%s %s%s%s %s%s%s" % (q1,self.args.pgm,q1, q2,full_path1,q2, q3,full_path2,q3)
                    d.add_row( (cmd, ))
                    diff_file_count += 1

            if diff_file_count:
                diffpgm_tbl = d.get_string(sortby="diff")
                print(diffpgm_tbl)
                print()

    #############################################################################

    def output_to_html(self, x:VeryPrettyTablePatched, dname1:str, dname2:str):
        """Display an basic HTML version of the VeryPrettyTablePatched table to the screen
           This should be redirected to a file.
           Ex: dcmp.py --html -r r:\a r:\b > results.htm

        Args:
            x: the VeryPrettyTablePatched containing rows that need to be displayed

            dname1: the first directory, used in the table's title

            dname2: the second directory, used in the table's title
        """
        tbl = x.get_html_string(sortby="fname")
        if not len(x._rows):
            return # do not output when there are no rows
        tbl = tbl.replace("<table>","<table>\n    <tr><td colspan='7'>1) %s</td></tr>\n    <tr><td colspan='7'>2) %s</td></tr>\n" % (dname1,dname2))
        tbl = tbl.replace("<table>", "<table border='1' cellspacing='3' cellpadding='3'>")
        print(tbl)
        print("<br /><hr noshade><br />")

#############################################################################

    def output_stats(self, x:VeryPrettyTablePatched):
        """Display the following information:
            same_meta, not_same_meta, exact_data, not_exact_data, same_meta_different_data
            program's runtime

        Args:
            x: a one row VeryPrettyTablePatched table containing this information
        """

        tbl = x.get_string()

        runtime = self.time_end - self.time_start
        m, s = divmod(runtime, 60)
        h, m = divmod(m, 60)

        width = 3*len(x._widths) + sum(x._widths) + 1

        print("-" * width,file=sys.stderr)
        cmd = " ".join(sys.argv)
        rt = "runtime (h:m:s) %02d:%02d:%02.2f" % (h,m,runtime)
        print("| %s %s |" % (cmd," " * (width - len(cmd)-5)),file=sys.stderr)
        print("| %s %s |" % (rt," " * (width - len(rt)-5)),file=sys.stderr)
        print(tbl, file=sys.stderr)
        print("",file=sys.stderr)

#############################################################################

    def output_stats_to_html(self, x:VeryPrettyTablePatched):
        """Display the following information:
            same_meta, not_same_meta, exact_data, not_exact_data, same_meta_different_data
            program's runtime

        Args:
            x: a one row VeryPrettyTablePatched table containing this information
        """

        tbl = x.get_html_string()
        if not len(x._rows):
            return # do not output when there are no rows
        
        cmd = " ".join(sys.argv)
        runtime = self.time_end - self.time_start
        m, s = divmod(runtime, 60)
        h, m = divmod(m, 60)
        
        tbl = tbl.replace("<table>","<table>\n    <tr><td colspan='5'>%s</td></tr>\n    <tr><td colspan='5'>runtime (h:m:s) %02d:%02d:%02.2f</td></tr>\n" % (cmd,h,m,runtime))
        tbl = tbl.replace("<table>", "<table border='1' cellspacing='3' cellpadding='3'>")
        print("")
        print(tbl)
        print("<br /><hr noshade><br />")
        print()

    # end of class: Dir_Compare
    ###########################

#############################################################################

if "__main__" == __name__:
    multiprocessing.freeze_support()
    MyManager.register('defaultdict', defaultdict, DictProxy)
    Dir_Compare()
