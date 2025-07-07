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

def process():
    print('Processing')

def do_freelist(cur):
    print('Free list...')
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

    # Get a cursor
    cur = cnx.cursor()

    if mode == 'A':
        print('Adding...')
        if host is None:
            print('No host specified')
        if ip is None:
            print('No IP specified. Using next available.')
            cur.execute('SELECT ip FROM ips WHERE host is null limit 1')
            if (cur.rowcount == 0):
                print('No free IPs available.')
                sys.exit(3)
            ip = cur.fetchone()
    elif mode == 'M':
        print('Modifying...')
        if host is None or ip is None:
            print('Must specifiy ')
    elif mode == 'D':
        print('Deleting...')
    elif mode == 'L':
        print('Getting...')
    elif mode == 'F':
        do_freelist(cur)
    else:
        usage('FATAL: Unknown mode')

    # Close connection
    cnx.close()

if __name__ == '__main__':
    main()