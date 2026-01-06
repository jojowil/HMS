#!/usr/bin/env python3

import getopt, sys, configparser, os, subprocess
import re, mysql.connector
from datetime import datetime

VERSION = "1.2.1-20260106"
CONFIG = "/etc/hms.ini"
FIXED = "/etc/hms.fixed"

def get_serial():
    return datetime.now().strftime("%y%m%d%H%M")


def bail():
    print('Something went wrong. See above for some kind of hint.')
    sys.exit(255)


def config_default_usage():
    print(f"Check the {CONFIG} file for valid options.\nSee sample below.")
    print("""
[DEFAULT]
Host = 127.0.0.1
DB = hms
User = hms
Pwd = pwd
Port = 3306
""")
    sys.exit(1)


def config_bind_dhcp_usage():
    print(f"Check the {CONFIG} file for valid options.\nSee sample below.")
    print("""
[BIND]
Domain = cs.skidmore.edu
Host = 141.222.36.200,141.222.36.196
NSList = ns1.cs.skidmore.edu,ns2.cs.skidmore.edu
Key = /root/.ssh/id_dnsbind
FwdZoneDestName = cs.skidmore.edu,/etc/bind/cs.skidmore.edu
# ip wildcard is optional to allow multiple reverse zones.
RevZoneDestName = 36.222.141.in-addr.arpa,/etc/bind/staged-36.222.141.in-addr.arpa,141.222.36.%%:37.222.141.in-addr.arpa,/etc/bind/staged-37.222.141.in-addr.arpa,141.222.37.%%
User = root
Port = 22
""")
    print("""
[DHCP]
Host = 141.222.36.200, 141.222.36.196
Key = /root/.ssh/id_dhcp
DestName = /etc/dhcp/dhcptail.conf
User = root
Port = 22
""")
    sys.exit(1)


def usage(msg=None):
    if msg is not None:
        print('\nERROR: ' + msg + '\n')
    print('''
Usage:  hms -A -h hostname [ -i ip ] [ -d description ] [ -m mac ] [ -x ]
        hms -C -c cname -h hostname
        hms -D { -h hostname | -i ip | -c cname }
        hms -F
        hms -L [ {-h hostname | -i ip} ]
        hms -M -h hostname [ -d description ] [ -m mac ] [ {-x|-X} ]
        hms -P
        hms -R { -h hostname | -c cname } -n newname
        hms -V
''')

    print('''
 -A => Add entry.
 -C => Create CNAME entry.
 -D => Delete entry. (Does not ask for confirmation!)
 -F => Display free list.
 -L => List entries.
 -M => Modify entry.
 -P => Publish DNS/DHCP to servers based on config stanza.
 -R => Rename host entry. (Does not ask for confirmation!)
 -V => Print version.
 -x => Mark entry to use DHCP.
 -X => Disable DHCP.
''')
    sys.exit(1)


def check_mac_inuse(cnx, mac):
    try:
        cur = cnx.cursor()
        cur.execute("SELECT mac FROM hms_ip WHERE mac = %s ", (mac,))
        cur.fetchone()
        return True if cur.rowcount > 0 else False
    except mysql.connector.Error as err:
        print('MySQL error: {}'.format(err))
        bail()


def check_host_inuse(cnx, host):
    try:
        cur = cnx.cursor()
        cur.execute("SELECT ip FROM hms_ip WHERE host = %s ", (host,))
        cur.fetchone()
        return True if cur.rowcount > 0 else False
    except mysql.connector.Error as err:
        print('MySQL error: {}'.format(err))
        bail()


def check_cname_inuse(cnx, cname):
    try:
        cur = cnx.cursor()
        cur.execute("SELECT ip FROM hms_cname WHERE cname = %s ", (cname,))
        cur.fetchone()
        return True if cur.rowcount > 0 else False
    except mysql.connector.Error as err:
        print('MySQL error: {}'.format(err))
        bail()


def check_ip_inuse(cnx, ip):
    try:
        cur = cnx.cursor()
        cur.execute("SELECT host FROM hms_ip WHERE ip = %s and host is not null", (ip,))
        cur.fetchone()
        return True if cur.rowcount > 0 else False
    except mysql.connector.Error as err:
        print('MySQL error: {}'.format(err))
        bail()

def perform_select(cnx, query):
    try:
        cur = cnx.cursor()
        # Execute a query
        cur.execute(query)
        return cur
    except mysql.connector.Error as err:
        print('MySQL error: {}'.format(err))
        bail()


def perform_update(cnx, query):
    try:
        cur = cnx.cursor()
        cur.execute(query)
        cnx.commit()
        affected_rows = cur.rowcount
        if affected_rows > 0:
            print(f"{affected_rows} record(s) updated successfully.")
        else:
            print("No records were updated, and that's kinda weird.")
    except mysql.connector.Error as err:
        print('MySQL error: {}'.format(err))
        bail()


def do_add(cnx, ip, host, desc, mac, dhcp):
    # mac is optional.
    if mac is None and dhcp == 'Y':
        usage('Cannot use DHCP without a mac!')

    # mac must not already exist.
    if mac is not None and check_mac_inuse(cnx, mac):
        print('MAC %s is already in use.' % mac)
        sys.exit(3)

    # host is required and unique.
    if host is None:
        usage('No host name specified.')
    elif check_host_inuse(cnx, host):
        print('Host %s is already in use.' % host)
        sys.exit(3)

    # desc is optional, but recommended.
    if desc is None:
        print('No description specified. You should really describe the purpose.')

    # if you cannot afford and IP, one will be provided for you.
    if ip is None:
        print('No IP specified. Using next available.')
        try:
            cur = cnx.cursor()
            cur.execute('SELECT ip FROM hms_ip WHERE host is null limit 1')
            ip = cur.fetchone()[0]
            if cur.rowcount == 0:
                print('No free IPs available.')
                sys.exit(3)
            print('Using free IP: {}'.format(ip))
        except mysql.connector.Error as err:
            print('MySQL error: {}'.format(err))
            bail()
    elif check_ip_inuse(cnx, ip):
        print('IP %s is already in use.' % ip)
        sys.exit(3)

    # let's get this query together now.
    query = "update hms_ip set host='%s'" % host
    if mac is not None:
        query += ",mac='%s'" % mac
    if desc is not None:
        query += ",descr='%s'" % desc
    if dhcp is not None:
        query += ",dhcp='%s'" % dhcp
    query += " where ip='%s'" % ip

    # ok, let's add this thing...
    #print(query)
    perform_update(cnx, query)


def do_cname(cnx, cname, host) :
    if cname is None or host is None:
        usage('No host name or CNAME target specified.')
    # any other checks needed here? This seems too easy.
    query = "insert into hms_cname (cname, host) values (%s, %s)" % (cname, host)
    perform_update(cnx, query)


def do_rename_host(cnx, host, newhost):
    if host is None or newhost is None:
        usage('No old name or new name specified.')
        sys.exit(3)
    if not check_host_inuse(cnx, host):
        usage('Host %s does not exist.' % host)
        sys.exit(3)

    query = "update hms_ip set host='%s' where host='%s'" % (newhost, host)
    perform_update(cnx, query)


def do_rename_cname(cnx, cname, newcname):
    if cname is None or newcname is None:
        usage('No old CNAME or new CNAME specified.')
        sys.exit(3)
    if not check_cname_inuse(cnx, cname):
        usage('CNAME %s does not exist.' % cname)
        sys.exit(3)

    query = "update hms_cname set cname='%s' where cname='%s'" % (newcname, cname)
    perform_update(cnx, query)


def do_modify(cnx, host, desc, mac, dhcp):
    if host is None:
        usage('No host name specified.')
    if desc is None and mac is None and dhcp is None:
        usage('What do you want to modify?')
    if check_mac_inuse(cnx, mac):
        print('MAC %s is already in use.' % mac)
        sys.exit(6)

    query = 'update hms_ip set '
    if mac is not None:
        query += "mac='%s'" % mac
    elif desc is not None:
        query += "descr='%s'" % desc
    elif dhcp is not None:
        query += "dhcp='%s'" % dhcp
    query += " where host='%s'" % host
    perform_update(cnx, query)


def do_delete(cnx, ip, host):
    # Mst provide one or the other.
    if (ip is None and host is None) or (ip is not None and host is not None):
        print('Must specify either ip or host.')
        sys.exit(5)
    # IP in use?
    if ip is not None and not check_ip_inuse(cnx, ip):
        print('IP %s is not in use.' % ip)
        sys.exit(5)
    # host in use?
    if host is not None and not check_host_inuse(cnx, host):
        print('Host %s does not exist.' % host)
        sys.exit(5)
    # get the ip if we only have the host
    if ip is None and host is not None:
        query = "select ip from hms_ip where host='%s'" % host
        try:
            cur = cnx.cursor()
            cur.execute(query)
            ip = cur.fetchone()
        except mysql.connector.Error as err:
            print('MySQL error: {}'.format(err))
            bail()

    query = "update hms_ip set host=null, descr=null, mac=null, dhcp='N' where ip='%s' and host is not null" % ip
    #print(query)
    perform_update(cnx, query)


def do_list(cnx, ip, host):
    if ip is not None and host is not None:
        print('Must specify either ip or host - not both.')
        sys.exit(4)
    if ip is None and host is None:
        query = 'select host, ip, mac, descr, dhcp from hms_ip where host is not null'
    else:
        query = 'select host, ip, mac, descr, dhcp from hms_ip where '
        if ip is not None:
            query += "ip = '%s'" % ip
        else:
            query += "host = '%s'" % host
    try:
        cur = cnx.cursor()
        cur.execute(query)
        for row in cur:
            if row is None:
                if ip is not None and host is not None:
                    print('No entry found with %s or %s' % (ip, host))
                else:
                    t = ip if ip is not None else host
                    print('No entry found with %s' % t)
            else:
                print('Host ', row[0])
                print('IP   ', row[1])
                if row[2] is not None:
                    formatted_mac = ":".join([row[2][i:i + 2] for i in range(0, 12, 2)])
                else:
                    formatted_mac = "NO MAC PROVIDED"
                print('MAC  ', formatted_mac)
                print('Desc ', row[3])
                print('DHCP ', row[4], '\n')
    except mysql.connector.Error as err:
        print('MySQL error: {}'.format(err))
        bail()


def do_freelist(cnx):
    print('Free list...')
    try:
        cur = cnx.cursor()
        # Execute a query
        cur.execute('SELECT ip from hms_ip where host is null')
        for row in cur:
            # Access data by index (e.g., row[0], row[1])
            print(f'FREE: {row[0]}')
        print('\nTotal free IPs is', cur.rowcount)
    except mysql.connector.Error as err:
        print('MySQL error: {}'.format(err))
        bail()


def do_version():
    print(f'hms {VERSION}\n')
    sys.exit(0)


def do_bind_publish(cnx, config):
    #
    # Get publish data from /etc/hms.ini
    #
    bhost = None
    bnlist = None
    bkey = None
    # FIXME - Multiple forward zones?
    bfwdzone = None
    bfwdname = None
    # Allow multiple reverse zones.
    brevzone = []
    brevname = []
    brevwild = []
    buser = None
    bport = None
    bdom = None

    # Get options from ini.
    try:
        # Config already established
        bhost = config.get('BIND', 'Host')
        bnlist = config.get('BIND', 'NSList')
        bkey = config.get('BIND', 'Key')
        f = config.get('BIND', 'FwdZoneDestName')
        bfwdzone = f.split(',')[0]
        bfwdname = f.split(',')[1]
        rev = config.get('BIND', 'RevZoneDestName').split(':')
        for r in rev:
            parts = r.split(',')
            brevzone.append(parts[0])
            brevname.append(parts[1])
            if len(parts) > 2:
                brevwild.append(parts[2])
            else:
                brevwild.append(None)
        buser = config.get('BIND', 'User')
        bport = config.get('BIND', 'Port')
        bdom = config.get('BIND', 'Domain')
    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        print(f"Configuration error: {e}")
        config_bind_dhcp_usage()
    except IndexError as e:
        print(f"Configuration error: Check zone entries. {e}")
        config_bind_dhcp_usage()
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        config_bind_dhcp_usage()

    nslist = ''
    for x in bnlist.split(','):
        nslist += f'@ IN NS {x}.\n'

    # Build files
    serial = get_serial()
    forward = f"""$TTL 5M;
;$ORIGIN	cs.skidmore.edu.
@		IN	SOA	ns1.cs.skidmore.edu. root.cs.skidmore.edu. (
				{serial}	; serial
				1200		; refresh 20M
				600	        ; retry 5M
				1209600	    ; expire 2W
				3600 )      ; NEG Cache TTL 1H
{nslist}

"""

    reversefixed = f"""$TTL 5M;
;$ORIGIN cs.skidmore.edu.
@               IN      SOA     localhost. root.cs.skidmore.edu. (
                                {serial}        ; serial
                                1200            ; refresh 20M
                                600             ; retry 5M
                                1209600         ; Expire 2W
                                3600 )          ; NEG cache TTL 1H

{nslist}

"""

    # Get fixed content, if exists.
    if os.path.exists(FIXED):
        with open(FIXED, 'r') as file:
            forward += '\n' + file.read() + '\n'

    # Add CNAME records
    cur = perform_select(cnx, 'SELECT cname, host from hms_cname where cname is not null')
    for row in cur:
        # cname IN CNAME target.host.dom.
        forward += f'{row[0]} IN CNAME {row[1]}.\n'

    # Add forward records
    cur = perform_select(cnx, 'SELECT host, ip from hms_ip where host is not null')
    for row in cur:
        # host IN CNAME x.x.x.x
        forward += f'{row[0]}\tIN\tA\t{row[1]}\n'

    # Create forward file
    # FIXME check for file access
    tmpfwd = '/tmp/forward.zone'
    with open(tmpfwd, 'w') as file:
        file.write(forward)

    # Push file to endpoint
    for h in bhost.split(','):
        # scp -i key {tmpfwd} h:{bfwdname}
        # Send forward
        cmd = f'scp -i {bkey} -P {bport} {tmpfwd} {buser}@{h}:{bfwdname}'
        run_command(cmd)

        # Test Zones.
        cmd = f'ssh -i {bkey} -p {bport} {buser}@{h} "named-checkzone {bfwdzone} {bfwdname}"'
        run_command(cmd)

    #
    # The REVERSE work is trickier.
    #

    for i in range(len(brevzone)):
        reverse = reversefixed
        add =''
        if brevwild[i] is not None:
            add = f" and ip like '{brevwild[i]}'"
        query = "SELECT host, ip from hms_ip where host is not null %s" % add
        cur = perform_select(cnx, query)
        # Add forward and reverse records
        for row in cur:
            pieces =row[1].split('.')
            reverse += f'{pieces[3]}.{pieces[2]}\tIN\tPTR\t{row[0]}.{bdom}.\n'

        # Create reverse file
        # FIXME check for file access
        tmprev = '/tmp/reverse.zone'
        with open(tmprev, 'w') as file:
            file.write(reverse)

        # Push files to endpoint
        for h in bhost.split(','):
            # scp -i key {tmpfwd} h:{bfwdname}
            # Send reverse
            cmd = f'scp -i {bkey} -P {bport} {tmprev} {buser}@{h}:{brevname[i]}'
            run_command(cmd)

            # Test Zones.
            cmd = f'ssh -i {bkey} -p {bport} {buser}@{h} "named-checkzone {brevzone[i]} {brevname[i]}"'
            run_command(cmd)


def run_command(cmd):
    print(f'Running command: {cmd}')
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout, result.stderr, result.returncode)
    if result.returncode != 0:
        bail()


def main():
    #
    # Get DB data from /etc/hms.ini
    #
    config = configparser.ConfigParser()

    # Silence warnings
    dbhost = None
    dbuser = None
    dbpass = None
    dbport = None
    dbname = None

    # Get options from ini.
    try:
        if not os.path.exists(CONFIG):
            raise FileNotFoundError(f"Configuration file '{CONFIG}' not found.")
        config.read(CONFIG)
        # Get default settings for DB
        dbpass = config.get('DEFAULT','Pwd')
        dbhost = config.get('DEFAULT','Host')
        dbuser = config.get('DEFAULT','User')
        dbport = config.get('DEFAULT','Port')
        dbname = config.get('DEFAULT','DB')
    except FileNotFoundError as e:
        print(f"Error: {e}")
        config_default_usage()
    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        print(f"Configuration error: {e}")
        config_default_usage()
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        config_default_usage()

    # try to get options
    opts=''  # remove opts not assigned warning!
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'ACMDLFPRVc:i:h:n:m:d:xX')
    except getopt.GetoptError as err:
        # print help information and exit:
        #print(err, '\n')  # will print something like 'option -a not recognized'
        usage("{}".format(err))

    ip = None
    host = None
    newhost = None
    mac = None
    desc = None
    cname = None
    dhcp = 'N'
    modeset = "ACMDLFPRV"
    mode = ""

    ipregex = '^(?:(?:25[0-5]|(?:2[0-4]|1\\d|[1-9]|)\\d)\\.?\\b){4}$'
    ipvalid = re.compile(ipregex)
    macregex = '^(?:[0-9a-fA-F]){12}$'
    macvalid = re.compile(macregex)
    fqdnregex ='^[a-zA-Z][a-zA-Z0-9\\.\\-]{1,254}$'
    fqdnvalid = re.compile(fqdnregex)
    hostregex ='^[a-zA-Z][a-zA-Z0-9\\-]{1,31}$'
    hostvalid = re.compile(hostregex)
    descregex = '^[\\ a-zA-Z0-9_\\-\\.]{1,255}$'
    descvalid = re.compile(descregex)

    for o, a in opts:
        opt = o[1:]
        #print(opt) #debug
        if modeset.find(opt) != -1:
            mode = mode + opt
        elif opt == 'i':
            ip = a
            if not ipvalid.match(ip):
                usage(ip + ' is not a valid IPv4 address')
        # FIXME
        elif opt == 'c':
            cname = a
            if not fqdnvalid.match(cname):
                usage(cname + ' is not a valid target FQDN')
        elif opt == 'h':
            host = a
            if not hostvalid.match(host):
                usage(host + ' is not a valid host name')
        elif opt == 'm':
            mac = a.replace(':', '').replace('-', '').replace('.', '')
            if not macvalid.match(mac):
                usage(mac + ' is not a valid MAC address')
        elif opt == 'n':
            newhost = a
            if not hostvalid.match(newhost):
                usage(newhost + ' is not a valid host name')
        elif opt == 'd':
            desc = a
            if not descvalid.match(desc):
                usage(desc + ' is not a valid description')
        elif opt == 'x':
            dhcp = 'Y'
        elif opt == 'X':
            dhcp = 'N'
        else:
            assert False, 'unhandled option'

    # process options
    #print('Mode is', mode) #debug
    if len(mode) > 1:
        usage('Choose one of add, modify, delete, list, free, or version.')

    if mode == 'V':
        do_version()

    # Connect to server
    try:
        cnx = mysql.connector.connect(
        host=dbhost,
        port=dbport,
        user=dbuser,
        database=dbname,
        password=dbpass)
    except mysql.connector.Error as err:
        print(f'Error connecting to MySQL: {err}')
        sys.exit(2)

    if mode == 'A':
        do_add(cnx, ip, host, desc, mac, dhcp)
    elif mode == 'M':
        do_modify(cnx, host, desc, mac, dhcp)
    elif mode == 'D':
        do_delete(cnx, ip, host)
    elif mode == 'L':
        do_list(cnx, ip, host)
    elif mode == 'F':
        do_freelist(cnx)
    # FIXME
    elif mode == 'C':
        do_cname(cnx, cname, host)
    # FIXME
    elif mode == 'R':
        do_rename_host(cnx, host, newhost)
    elif mode == 'P':
        config = configparser.ConfigParser()
        config.read(CONFIG)
        dobind = config.has_section('BIND')
        dodhcp = config.has_section('DHCP')

        if not dobind and not dodhcp:
            print("No BIND or DHCP section found.")
            config_bind_dhcp_usage()

        if dodhcp:
            print("DHCP is not yet implemented.")  # do dhcp push
            # do_dhcp_publish(cnx, config)

        if dobind:
            do_bind_publish(cnx, config)
    else:
        usage('FATAL: Unknown mode')

    # Close connection
    cnx.close()


if __name__ == '__main__':
    main()
