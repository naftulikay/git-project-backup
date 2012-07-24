#!/usr/bin/env python2.7

import argparse, os, shutil, subprocess, sys, tempfile

def main():
    # parse our arguments
    arguments = parse_arguments()

    # validate that we're talking about real projects
    validate_projects(arguments.project)

    # create archives
    create_archives(arguments.project, arguments.ignored, arguments.output_dir)

    # encrypt archives
    if arguments.encrypt:
        encrypt_archives(arguments.project, arguments.keep, arguments.keys)

def parse_arguments():
    parser = argparse.ArgumentParser(
            description="Creates a backup of a given project based on its " +
                "Git and Maven project information with optional encryption.")
    parser.add_argument("project", nargs="+", type=str,
            help="The project directory/directories to create archives for.")
    parser.add_argument("-e", "--encrypt", action="store_true", dest="encrypt",
            help="Encrypt the project using GPG. To keep the original unencrypted " +
                "archive, see the '-k' option.")
    parser.add_argument("--encryption-key", action="append", metavar="KEY_NAME", dest="keys",
            default=[],
            help="Encryption key names to use when encrypting the files. Only useful " + 
                "when -e is passed. At least one key must be passed and must be the " +
                "valid name of an installed GPG encryption key.")
    parser.add_argument('-k', '--keep-archive', action="store_true", dest="keep",
            help="When encrypting the archive, keep the original zip file rather " +
                "than deleting it after encryption.")
    parser.add_argument("-o", "--output-dir", dest="output_dir", type=str, default="./",
            help="The output directory in which to place archive files. Defaults " +
                "to the current directory in which the script is executed from.")
    parser.add_argument("-i", "--include-ignored", action="store_true", dest="ignored",
            help="Include files ignored by .gitignore in the archive rather than " +
                "excluding them, which is the default functionality.")

    arguments = parser.parse_args()

    # validate the directories as being real and extant
    for i in range(len(arguments.project)):
        if os.path.isdir(arguments.project[i]):
            arguments.project[i] = {'rel': arguments.project[i], 
                    'abs': os.path.abspath(arguments.project[i]),
                    'base': os.path.basename(os.path.abspath(arguments.project[i])) }
        else:
            sys.stderr.write("ERROR: Unable to locate project directory: %s\n" % (
                    arguments.project[i],))
            parser.print_usage(sys.stderr)
            
            sys.exit(1)
   
    # validate that if we're encrypting that we've got recipients
    if arguments.encrypt and len(arguments.keys) < 1:
        sys.stderr.write("ERROR: When encrypting, you must pass the name of at least " +
                "encryption key with the --encryption-key argument.\n")
        parser.print_usage(sys.stderr)
        sys.exit(1)
    
    return arguments

def validate_projects(projects):
    for project in projects:
        if not os.path.isdir(os.path.join(project['abs'], '.git')):
            sys.stderr.write("ERROR: Project does not have a Git repository: %s\n" % (
                    project['rel'],))
            sys.exit(1)

def create_archives(projects, include_ignored=False, output_dir="./"):
    tmpdir = tempfile.mkdtemp()

    for project in projects:
        project['tmpdir'] = os.path.join(tmpdir, project['base'])
        
        # either copy it without ignored files or not
        if not include_ignored:
            subprocess.Popen(["/usr/bin/git", "clone", project['abs'], 
                project['tmpdir']], stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, close_fds=True).wait()
        else:
            shutil.copytree(project['abs'], project['tmpdir'])
        
        git_revision = subprocess.Popen(["/usr/bin/git", "rev-parse", "HEAD"],
            cwd=project['abs'], stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, close_fds=True).stdout.read().strip()
        
        git_tag = subprocess.Popen(["/usr/bin/git", "describe", "--exact-match", "--abbrev=0"],
            cwd=project['abs'], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, close_fds=True).stdout.read().strip()

        git_filename_info = git_revision[:8] if len(git_tag) == 0 else ("%s.%s" % (
            git_tag, git_revision[:8]))
        
        project['archive'] = os.path.join(tmpdir, "%s.%s.7z" % (project['base'], 
            git_filename_info))
        
        # generate the archive
        subprocess.Popen(["/usr/bin/7z", "a", "-t7z", "-m0=lzma", "-mx=9", 
            project['archive'], project['tmpdir']], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, close_fds=True).wait()

        # remove the project tmp dir
        shutil.rmtree(project['tmpdir'])

        # move the project archive to the output directory
        project['output'] = os.path.join(output_dir, 
                os.path.basename(project['archive']))

        shutil.move(project['archive'], project['output'])

    # remove the tmp dir
    os.rmdir(tmpdir)

def encrypt_archives(projects, keep_archives=False, recipients=None):
    archives = [project['output'] for project in projects]

    # encrypt the archives
    gpg_args = ["/usr/bin/gpg", "--yes", "--trust-model", "always", "--encrypt-files"]
   
    for recipient in recipients:
        gpg_args.append("--recipient")
        gpg_args.append(recipient)
    
    gpg_args.extend(archives)

    subprocess.Popen(gpg_args, stdout=subprocess.PIPE, stderr=sys.stderr,
            close_fds=True).wait()
    
    # remove the archives 
    if not keep_archives:
        for archive in archives:
            os.remove(archive)

if __name__ == "__main__":
    main()
