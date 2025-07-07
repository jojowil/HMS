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

The rules are pretty simple, and the options are self-explanatory. The code could use some additional documentation, but I was more concerned about ensuring data validation and minimizing injection opportunities. This project has a rather special purpose, but it was enjoyable to write. After the DB tool is complete, I'll add options to push to DNS and DHCP servers by replacing their basic config files using includes.

The options are coming along, but are still being refined.

```
Usage: { -A | -M | -D | -L | -F } -i ip -h hostname -d "description" -m mac -x


        -A [ -i ip ] -h hostname [ -m mac ] [ -d "description" ] [ -x ]
        -M -i ip [ -h hostname | -m mac | -d "description" | -x ]
        -D -i ip | -h hostname
        -L -i ip | -h hostname
        -F
```

Some examples are shown below.

```bash
python3 hms.py -A -i 141.222.36.5 -h newhost -d "Sooper Dooper" -m abcd.1234.98ED -x
```
