import getopt, sys
import re, mysql.connector

# Delete -> update hms_ip set host = null where host = ?? or ip = ??
# modify ->

def usage(msg=None):
    if msg is not None:
        print('\nERROR: ' + msg + '\n')
    print('Usage: { -A | -M | -D | -L | -F } -i ip -h hostname -d "description" -m mac -x\n')
    print("\n\t-A add\n\t-M modify\n\t-D delete\n\t-L list\n\t-F free list\n")
    sys.exit(1)

def check_host_inuse(cnx, host):
    cur = cnx.cursor()
    cur.execute("SELECT COUNT(*) FROM hms_ip WHERE host = %s ", (host,))
    inuse = True if cur.rowcount > 0 else False
    # must fetch or unread result
    cur.fetchall()
    return inuse

def check_ip_inuse(cnx, ip):
    cur = cnx.cursor()
    cur.execute("SELECT COUNT(*) FROM hms_ip WHERE ip = %s and host is not null", (ip,))
    inuse = True if cur.rowcount > 0 else False
    # must fetch or unread result
    cur.fetchall()
    return inuse


def do_add(cnx, ip, host, desc, mac, dhcp):
    print('Adding...')
    cur = cnx.cursor()
    # mac is optional
    if mac is None and dhcp == 'Y':
        print('Cannot use DHCP without a mac!')
        sys.exit(3)
    # host is required and unique
    if host is None:
        print('No host name specified.')
        sys.exit(3)
    elif check_host_inuse(cnx, host):
            print('Host %s is already in use.' % host)
            sys.exit(3)
    # desc is optional, but recommended.
    if desc is None:
        print('No description specified. You should really describe the purpose.')
    # if you cannot afford and IP, one will be provided for you.
    if ip is None:
        print('No IP specified. Using next available.')
        cur.execute('SELECT ip FROM hms_ip WHERE host is null limit 1')
        if cur.rowcount == 0:
            print('No free IPs available.')
            sys.exit(3)
        ip = cur.fetchone()
    else:
        if check_ip_inuse(cnx, ip):
            print('IP already in use.')
            sys.exit(3)
    query = "update hms_ip set host='%s'" % (host)
    if mac is not None:
        query += ",mac='%s'" % (mac)
    if desc is not None:
        query += ",descr='%s'" % (desc)
    if dhcp is not None:
        query += ",dhcp='%s'" % (dhcp)
    query += " where ip='%s';" % (ip)

    print(query)
    cur.execute(query)
    cnx.commit()

    # Check the number of affected rows
    affected_rows = cur.rowcount

    if affected_rows > 0:
        print(f"{affected_rows} record(s) updated successfully.")
    else:
        print("No records were updated (either no matching rows or data was already the same).")

def do_modify(cnx, ip, desc, mac, dhcp):
    return

def do_delete(cnx, ip, desc, mac):
    print('Deleting...')
    return

def do_list(cnx, ip, host):
    if (ip is None and host is None) or (ip is not None and host is None):
        print('Must specify either ip or host.')
        sys.exit(4)
    query = 'select * from hms_ip where '
    if ip is not None:
        query += "ip = '%s'" % (ip)
    else:
        query += "host = '%s'" % (host)
    cur = cnx.cursor()
    cur.execute(query)
    return

def do_freelist(cnx):
    print('Free list...')
    cur = cnx.cursor()
    # Execute a query
    cur.execute('SELECT ip from hms_ip where host is null')
    for row in cur:
        # Access data by index (e.g., row[0], row[1])
        print(f'FREE: {row[0]}')
    print('\nTotal free IPs is', cur.rowcount)

def main():
    #
    # Get password for user with table access
    #
    pfile = '/etc/security/mydbpw'
    try:
        f = open(pfile, 'r')
        dbpwd = f.read().strip()
    except IOError:
        print('Cannot open', pfile, '.')
        sys.exit(3)
    f.close()

    # try to get options
    opts=''  # remove opts not assigned warning!
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'AMDLFi:h:m:d:x')
    except getopt.GetoptError as err:
        # print help information and exit:
        print(err)  # will print something like 'option -a not recognized'
        usage()

    output = None
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
        elif opt == 'm':
            mac = a.replace(':', '').replace('-', '').replace('.', '')
            if not macvalid.match(mac):
                usage(mac + ' is not a valid MAC address')
        elif opt == 'd':
            desc = a
            print(desc)
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
        print('Modifying...')
        if host is None or ip is None:
            print('Must specifiy ')
    elif mode == 'D':
        do_delete(cnx, host)
    elif mode == 'L':
        print('Getting...')
    elif mode == 'F':
        do_freelist(cnx)
    else:
        usage('FATAL: Unknown mode')

    # Close connection
    cnx.close()

if __name__ == '__main__':
    main()