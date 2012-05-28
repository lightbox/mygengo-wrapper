#!/usr/bin/env python
import os
import sys
import shutil
from zipfile import ZipFile
from subprocess import check_call, Popen, PIPE
import json

# Master PO files are created from English, processed, then copied to I18N_UP_DIR
# ready to be uploaded to MyGengo

# Completed translations can be imported from I18N_DOWN_WEB_DIR
HOME = os.environ['HOME']
I18N_UP_DIR = os.path.join(HOME, "tmp/i18n_up")
I18N_DOWN_WEB_DIR = os.path.join(HOME, "tmp/i18n_down_web")

# PO files are searched in WEB_DIR and JS dir
SERVER_DIR = os.path.join(HOME, "%s/../../" % os.getcwd())
WEB_DIR = os.path.join(SERVER_DIR, "web/locale/%s/LC_MESSAGES")
JS_DIR = os.path.join(SERVER_DIR, "html/locale/%s/LC_MESSAGES")

# English PO file copied here
MASTER_WEB_PO = os.path.join(SERVER_DIR, "web/locale/master/django.po")
MASTER_JS_PO = os.path.join(SERVER_DIR, "html/locale/master/djangojs.po")

def to_mygengo():
    ensure_dir(I18N_UP_DIR)
    # Make new messages, copy to master dir
    check_call(["python", "manage.py", "makemessages_14", "-a", "-e py,html", "--no-wrap", "-i", "dashboard.py"], stdout=PIPE, cwd=os.path.join(SERVER_DIR, "web")
    check_call(["python", "../web/manage.py", "makemessages_14", "-a", "-d", "djangojs", "-i", 'CACHE/*', "--no-wrap"], stdout=PIPE, cwd=os.path.join(SERVER_DIR, "html")

    for orig, dest in [(os.path.join(JS_DIR % "en", "djangojs.po"), MASTER_JS_PO),
                       (os.path.join(WEB_DIR % "en", "django.po"), MASTER_WEB_PO)]:
        with open(orig) as f:
            buf = f.read()

        buf = _convert_to_master(buf)
        with open(dest, "w") as f:
            f.write(buf)

    # Copy language files to tmp directory
    for orig, dest in [("html/locale/master/djangojs.po", "djangojs.po.orig"),
                       ("web/locale/master/django.po", "django.po.orig"),]:
        shutil.copy(os.path.join(SERVER_DIR, orig), os.path.join(I18N_UP_DIR, dest))

    # Convert po files
    for po_file in ["django.po", "djangojs.po"]:
        plural_to_single(os.path.join(I18N_UP_DIR, po_file + '.orig'), os.path.join(I18N_UP_DIR, po_file))

    # Print instructions
    print """
To finish uploading:

Go to http://mygengo.com - import
Upload:
    %(home)s/django.po
    %(home)s/djangojs.po
    """ % {'home': os.path.join(HOME, I18N_UP_DIR)}

def _convert_to_master(buf):
    """Overwrite msgstr with msgid
    """
    sub = Popen(["msgen", "-", "--no-wrap"], stdin=PIPE, stdout=PIPE)
    buf = sub.communicate(buf)[0]
    if sub.returncode:
        raise Exception, "msgen error"
    return buf

def from_mygengo_web():
    try:
        lang_files = os.path.join(I18N_DOWN_WEB_DIR, "lang_files.zip")
        ZipFile(lang_files).extractall(I18N_DOWN_WEB_DIR)
    except:
        print """
Missing web language pack

Go to http://mygengo.com -> dashboard
Download files: All languages
Save as: %s/lang_files.zip
""" % os.path.join(HOME, I18N_DOWN_WEB_DIR)
        sys.exit(1)

    languages = [lang for lang in os.listdir(I18N_DOWN_WEB_DIR) if lang not in ['en', 'lang_files.zip', '.DS_Store']]
    for lang in languages:
        # Convert po files
        for po_file, master in [("django.po", MASTER_WEB_PO), ("djangojs.po", MASTER_JS_PO)]:
            updated = os.path.join(I18N_DOWN_WEB_DIR, lang, po_file)
            orig = os.path.join(I18N_DOWN_WEB_DIR, lang, po_file + '.orig')
            shutil.move(updated, orig)
            with open(orig) as f:
                buf = f.read()

            buf = single_to_plural(buf, master, orig)

            with open(updated, "w") as f:
                f.write(buf)

        for po_file, dest_dir in [('django.po', WEB_DIR % lang),
                                  ('djangojs.po', JS_DIR % lang)]:
            ensure_dir(dest_dir)
            orig = os.path.join(I18N_DOWN_WEB_DIR, lang, po_file)
            dest = os.path.join(dest_dir, po_file)
            shutil.copy(orig, os.path.join(dest_dir, dest))

    # Compile
    check_call(["python", "manage.py", "compilemessages"], stdout=PIPE, cwd=os.path.join(SERVER_DIR, "web")
    check_call(["python", "../web/manage.py", "compilemessages"], stdout=PIPE, cwd=os.path.join(SERVER_DIR, "html"))

# NOTE: Does not handle multiple line plurals
def single_to_plural(buf, master, orig):
    with open(master) as f:
        master_po = [line for line in f]
    split_buf = buf.split("\n")

    for num, line in enumerate(master_po):
        if line.startswith("msgid_plural"):
            singular_msgid = master_po[num - 1].strip()
            assert singular_msgid.startswith("msgid"), "ERROR: Multi-line plural in %s:%s: %s" % (master_po,
                                                                                                  num + 1, line)
            line_no = _line_no_of_match(split_buf, singular_msgid)
            if line_no <= 0:
                "WARNING: %s: Could not find matching msgid: %s" % (orig, singular_msgid)
                continue
            singular_str = "msgstr[0] " + split_buf[line_no + 2].strip()
            # remove from file
            for i in range(4):
                split_buf.pop(line_no)
            plural_msgid_orig = line.strip()
            plural_msgid = plural_msgid_orig.replace("msgid_plural", "msgid")
            line_no = _line_no_of_match(split_buf, plural_msgid)
            plural_str = "msgstr[1] " + split_buf[line_no + 2].strip()
            # remove from file
            for i in range(4):
                split_buf.pop(line_no)

            details = {"sing_msgid": singular_msgid,
                       "sing_str": singular_str,
                       "plu_msgid": plural_msgid_orig,
                       "plu_str": plural_str,
                      }

            split_buf.insert(line_no, "%(sing_msgid)s\n%(plu_msgid)s\n%(sing_str)s\n%(plu_str)s\n" % details)

    return "\n".join(split_buf)

def _line_no_of_match(lines, line_to_match):
    line_no = -1
    for num, line in enumerate(lines):
        if line_to_match in line:
            line_no = num
            break
    return line_no

def _get_translation(rest_of_file, match_line):
    for rev_num, line in enumerate(rest_of_file[::-1]):
        if line == match_line:
            next_line = rest_of_file[-rev_num]
            assert next_line.startswith("msgstr \""), "ERROR: Expected to find msgstr line %s: found %s" % (len(rest_of_file) - rev_num, next_line)
            return next_line

def plural_to_single(local_po_file, mygengo_file):
    with open(local_po_file) as f:
        local_po = [line for line in f]

    to_append = []
    for num, line in enumerate(local_po):
        if line.find("msgid_plural") >= 0:

            singular_msgid = local_po[num - 1]
            assert singular_msgid.startswith("msgid"), "ERROR: Multi-line plural in %s:%s: %s" % (local_po_file, num + 1, line)
            plural_msgid = line.replace("msgid_plural", "msgid")
            singular_line = local_po[num + 1] .replace("msgstr[0]", "msgstr")
            plural_line = local_po[num + 2] .replace("msgstr[1]", "msgstr")
            to_append.extend(_copy_to_end(singular_msgid, singular_line))
            to_append.extend(_copy_to_end(plural_msgid, plural_line))

    local_po.extend(to_append)
    with open(mygengo_file, "w") as f:
        f.writelines(local_po)

def _copy_to_end(msgid, trans):
    to_append = []
    to_append.append("\n")
    to_append.append("# Generated by mygengo convert\n")
    to_append.append(msgid)
    to_append.append(trans)
    return to_append

def ensure_dir(dir_name):
    try:
        os.makedirs(dir_name)
    except OSError as e:
        # Already exists
        if not e[0] == 17:
            raise

def usage():
    return """
Usage: python mygengo_convert <command>

Commands:
    export      prepare strings for upload to mygengo
    import      retrieve new translations from mygengo
"""

if __name__ == "__main__":
    if len(sys.argv) == 1:
        print usage()
    elif sys.argv[1] == "export":
        to_mygengo()
    elif sys.argv[1] == "import":
        from_mygengo_web()
    else:
        print usage()

