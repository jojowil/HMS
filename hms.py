#!/usr/bin/env python3

import getopt, sys
import re, mysql.connector

# Delete -> update hms_ip set host = null where host = ?? or ip = ??
# modify ->


def bail():
    print('Something went wrong. See above for some kind of hint.')
    sys.exit(255)


def usage(msg=None):
    if msg is not None:
        print('\nERROR: ' + msg + '\n')
    print('Usage:  hms -A -h hostname [ -i ip ] [ -d description ] [ -m mac] [ -x ]')
    print('        hms -M -h hostname { -d description | -m mac] | -x } [...]')
    print('        hms { -D | L } -h hostname | -i ip')
    print('        hms -F\n')
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


def do_modify(cnx, host, desc, mac, dhcp):
    if host is None:
        usage('No host name specified.')
    if desc is None and mac is None and dhcp is None:
        usage('What do you want to modify?')
    if check_mac_inuse(cnx, mac):
        print('MAC %s is already in use.' % mac)
        sys.exit(5)

    query = 'update hms_ip'
    if mac is not None:
        query += ",mac='%s'" % mac
    if desc is not None:
        query += ",descr='%s'" % desc
    if dhcp is not None:
        query += ",dhcp='%s'" % dhcp
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
    if (ip is None and host is None) or (ip is not None and host is not None):
        print('Must specify either ip or host.')
        sys.exit(4)
    query = 'select host, ip, mac, descr, dhcp from hms_ip where '
    if ip is not None:
        query += "ip = '%s'" % ip
    else:
        query += "host = '%s'" % host
    try:
        cur = cnx.cursor()
        cur.execute(query)
        row = cur.fetchone()
        if row is None:
            if ip is not None and host is not None:
                print('No entry found with %s or %s' % (ip, host))
            else:
                t = ip if ip is not None else host
                print('No entry found with %s' % (t))
        else:
            print('Host ', row[0])
            print('IP   ', row[1])
            print('MAC  ', row[2])
            print('Desc ', row[3])
            print('DHCP ', row[4])
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


def main():
    #
    # Get password for user with table access
    #
    pfile = '/etc/security/mydbpw'
    try:
        f = open(pfile, 'r')
        dbpwd = f.read().strip()
    except IOError:
        print('Cannot open ' + pfile + '.')
        sys.exit(3)
    f.close()

    # try to get options
    opts=''  # remove opts not assigned warning!
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'AMDLFi:h:m:d:x')
    except getopt.GetoptError as err:
        # print help information and exit:
        #print(err, '\n')  # will print something like 'option -a not recognized'
        usage("{}".format(err))

    ip = None
    host = None
    mac = None
    desc = None
    dhcp = 'N'
    modeset = "AMDLF"
    mode = ""

    ipregex = '^(?:(?:25[0-5]|(?:2[0-4]|1\\d|[1-9]|)\\d)\\.?\\b){4}$'
    ipvalid = re.compile(ipregex)
    macregex = '^(?:[0-9a-fA-F]){12}$'
    macvalid = re.compile(macregex)
    hostregex ='^[a-zA-Z][a-zA-Z0-9\\-]{1,31}$'
    hostvalid = re.compile(hostregex)
    descregex = '^[\\ a-zA-Z0-9_\\-\\.]{1,31}$'
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
        elif opt == 'h':
            host = a
            if not hostvalid.match(host):
                usage(host + ' is not a valid host name')
        elif opt == 'm':
            mac = a.replace(':', '').replace('-', '').replace('.', '')
            if not macvalid.match(mac):
                usage(mac + ' is not a valid MAC address')
        elif opt == 'd':
            desc = a
            if not descvalid.match(desc):
                usage(desc + ' is not a valid description')
        elif opt == 'x':
            dhcp = 'Y'
        else:
            assert False, 'unhandled option'

    # process options
    #print('Mode is', mode) #debug
    if len(mode) > 1:
        usage('Choose one of add, modify, delete, list, or free.')

    # Connect to server
    try:
        cnx = mysql.connector.connect(
        host='127.0.0.1',
        port=3306,
        user='hms',
        database='hms',
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
    else:
        usage('FATAL: Unknown mode')

    # Close connection
    cnx.close()


if __name__ == '__main__':
    main()