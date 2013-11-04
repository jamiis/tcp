tcp
=======

a (very) basic implementation of tcp.
made for columbia's computer networks class.

contents:
    application:
        application layer client and server from comp. networks prog. assignment 1
    network: 
        network layer implementation of tcp (with selective repeat) on top of udp.

CHANGE ME:
howto run:
server:
    > python server.py <port>
client:
    > python client <ip of server> <port>

running server.py will print out the ip on which server.py is listening.
use that ip when running the client. make sure port numbers match and the
port is available.

commands:
    whoelse
        -what other users are currently connected to the server
    wholasthr
        -which users have connected to the server in the past hour
    broadcast <message>
        -broadcast a message to all logged-in users
    exit
        -close the connection with the server

closing notes:
-please use the exit command to close a socket or else you will encounter errors.
-whoelse and wholasthr report sets of usernames, meaning no duplicate entries. 
 if user A logs in, logs out, then logs in again, wholasthr will list user A once. 
-users can login multiple times. if a user is logged in on two machines, whoelse
 will still only list that user once.
