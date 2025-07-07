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
```

The rules are pretty simple, and the options are fairly self-explanatory. The code could use some more documentation, but I was more concerned about making sure there was data validation and reduced injection opportunities. This project is rather special purpose, but it was fun to write. After the DB tool is complete, I'll add options to push to DNS and DHCP servers by replacing their basic config files using includes.
