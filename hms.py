#!/usr/bin/env python3

import getopt, sys, configparser, os
import re, mysql.connector


VERSION = "1.1.0-20251106"
CONFIG = "/etc/hms.ini"


def bail():
    print('Something went wrong. See above for some kind of hint.')
    sys.exit(255)


def config_usage():
    print(f"Check the {CONFIG} file for valid options.\nSee sample below.")
    print("\n[DEFAULT]\nHost = 127.0.0.1\nDB = hms\nUser = hms\nPwd = pwd\nPort = 3306")
    sys.exit(1)


def usage(msg=None):
    if msg is not None:
        print('\nERROR: ' + msg + '\n')
    print('Usage:  hms -A -h hostname [ -i ip ] [ -d description ] [ -m mac ] [ -x ]')
    print('        hms -M -h hostname [ -d description ] [ -m mac ] [ {-x|-X} ]')
    print('        hms -D { -h hostname | -i ip | -c cname }')
    print('        hms -L [ {-h hostname | -i ip} ]')
    print('        hms -R -h hostname -n newname')
    print('        hms -C -c cname -h hostname')
    print('        hms -F')
    print('        hms -V\n')
    print(" -A => Add entry.\n -M => Modify entry.\n -D => Delete entry. (Does not ask for confirmation!)")
    print(" -R => Rename host entry. (Does not ask for confirmation!)")
    print(" -C => Create CNAME entry.")
    print(" -L => List entries.\n -F => Display free list.\n -V => Print version.")
    print(" -x => Mark entry to use DHCP.\n -X => Disable DHCP.\n")
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


def check_ip_inuse(cnx, ip):
    try:
        cur = cnx.cursor()
        cur.execute("SELECT host FROM hms_ip WHERE ip = %s and host is not null", (ip,))
        cur.fetchone()
        return True if cur.rowcount > 0 else False
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


def do_rename(cnx, host, newhost):
    if host is None or newhost is None:
        usage('No old name or new name specified.')
        sys.exit(3)
    if not check_host_inuse(cnx, host):
        usage('Host %s does not exist.' % host)
        sys.exit(3)

    query = "update hms_ip set host='%s' where host='%s'" % (newhost, host)
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
        print('Host %s does not.' % host)
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


def main():
    #
    # Get DB data from /etc/hms.ini
    #
    config = configparser.ConfigParser()

    try:
        if not os.path.exists(CONFIG):
            raise FileNotFoundError(f"Configuration file '{CONFIG}' not found.")
        config.read(CONFIG)
        # Access configuration values here
        dbpwd = config.get('DEFAULT','Pwd')
        dbhost = config.get('DEFAULT','Host')
        dbuser = config.get('DEFAULT','User')
        dbport = config.get('DEFAULT','Port')
        dbname = config.get('DEFAULT','DB')
    except FileNotFoundError as e:
        print(f"Error: {e}")
        config_usage()
    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        print(f"Configuration error: {e}")
        config_usage()
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        config_usage()

    # try to get options
    opts=''  # remove opts not assigned warning!
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'ACMDLFRVc:i:h:n:m:d:xX')
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
    modeset = "ACMDLFRV"
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
        do_version();

    # Connect to server
    try:
        cnx = mysql.connector.connect(
        host=dbhost,
        port=dbport,
        user=dbuser,
        database=dbname,
        password=dbpwd)
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
    elif mode == 'C':
        do_cname(cnx, cname, host)
    elif mode == 'R':
        do_rename(cnx, host, newhost)
    else:
        usage('FATAL: Unknown mode')

    # Close connection
    cnx.close()


if __name__ == '__main__':
    main()
