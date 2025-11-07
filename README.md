# HMS

## Host Management System

The Host Management System (HMS) is a simple tool that utilizes command-line options to manage a basic database of IP addresses, MAC addresses, hostnames, and limited DHCP capabilities.

The database is equally primitive, consisting of two tables:

```sql
create database hms;

use hms;

create table hms_ip(
    host varchar(32) unique
    , mac varchar(12) unique
    , ip varchar(15) unique
    , descr varchar(256)
    , dhcp enum('Y', 'N')
);

create table hms_cname(
    cname varchar(32)
    , host varchar(255)
);

create user 'hms'@'localhost' identified by 'sooperdooperpassword!';

grant all on hms.* to 'hms'@'localhost';
```

A configuration file is expected to be located at */etc/hms.ini*.

```ini
[DEFAULT]
Host = 127.0.0.1
DB = hms
User = hms
Pwd = pwd
Port = 3306
```

The rules are pretty simple, and the options are self-explanatory. The code could use some additional documentation, but I was more concerned about ensuring data validation and minimizing injection opportunities. This project has a rather special purpose, but it was enjoyable to write. After the DB tool is complete, I'll add options to push to DNS and DHCP servers by replacing their basic config files using includes.

The options are coming along, but are still being refined.

```
Usage:  hms -A -h hostname [ -i ip ] [ -d description ] [ -m mac ] [ -x ]
        hms -M -h hostname [ -d description ] [ -m mac ] [ {-x|-X} ]
        hms -D { -h hostname | -i ip | -c cname }
        hms -L [ {-h hostname | -i ip} ]
        hms -R -h hostname -n newname
        hms -C -c cname -h hostname
        hms -F
        hms -V

 -A => Add entry.
 -M => Modify entry.
 -D => Delete entry. (Does not ask for confirmation!)
 -R => Rename host entry. (Does not ask for confirmation!)
 -C => Create CNAME entry.
 -L => List entries.
 -F => Display free list.
 -V => Print version.
 -x => Mark entry to use DHCP.
 -X => Disable DHCP.
```

Some examples are shown below.

```bash
hms.py -A -i 141.222.36.5 -h newhost -d "Sooper Dooper" -m abcd.1234.98ED -x
hms.py -C -c alsohost -h host.example.com
hms.py -D -i 166.32.44.210
```
