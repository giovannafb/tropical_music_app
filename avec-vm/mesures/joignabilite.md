# Version VM — matrice de joignabilité (étape 10)

Relevée le 26/10/2026 à 21:46 par `bash avec-vm/joignabilite.sh`, les trois VM démarrées et tous leurs services actifs
(une tentative qui échoue échoue donc faute de route ou de règle, et non parce qu'un service est arrêté).
Chaque case est une connexion TCP (`nc -z -w 2` depuis une VM, `/dev/tcp` depuis l'hôte) ; en gras, un écart à l'attendu du sujet.

| Depuis | vers proxy :80 (192.168.56.11) | vers métier :8000 (192.168.56.12) | vers base :3306 (192.168.56.13) |
|---|:---:|:---:|:---:|
| **L'hôte** (WSL, 192.168.56.1) | oui ; via 127.0.0.1:8081 : oui | non | non |
| **vm-presentation** | — | oui | non |
| **vm-metier** | **non** (attendu : oui) | — | oui |
| **vm-donnees** | **non** (attendu : oui) | **non** (attendu : oui) | — |

Autres services de vm-donnees, depuis l'hôte (doivent échouer) : Redis 6379 : non ; Elasticsearch 9200 : non.
Redirections de port de la carte NAT (sur 127.0.0.1 de l'hôte uniquement) : site 8081 → vm-presentation:80 ; Mailpit 8027 → vm-metier:8025 : oui.

## Adresses d'écoute (`ss -tlnp`, ports de l'application)

### vm-donnees (192.168.56.13)

```
State  Recv-Q Send-Q          Local Address:Port  Peer Address:PortProcess                                                  
LISTEN 0      151             192.168.56.13:3306       0.0.0.0:*    mysqld
LISTEN 0      511                 127.0.0.1:6379       0.0.0.0:*    redis-server
LISTEN 0      64                    0.0.0.0:2049       0.0.0.0:*                                                            
LISTEN 0      511             192.168.56.13:6379       0.0.0.0:*    redis-server
LISTEN 0      4096       [::ffff:127.0.0.1]:9300             *:*    java
LISTEN 0      4096   [::ffff:192.168.56.13]:9300             *:*    java
LISTEN 0      4096                    [::1]:9300          [::]:*    java
LISTEN 0      4096                    [::1]:9200          [::]:*    java
LISTEN 0      64                       [::]:2049          [::]:*                                                            
LISTEN 0      4096   [::ffff:192.168.56.13]:9200             *:*    java
LISTEN 0      4096       [::ffff:127.0.0.1]:9200             *:*    java
```

### vm-metier (192.168.56.12)

```
State  Recv-Q Send-Q Local Address:Port Peer Address:PortProcess                                                                               
LISTEN 0      4096       127.0.0.1:1025      0.0.0.0:*    mailpit
LISTEN 0      2048   192.168.56.12:8000      0.0.0.0:*    gunicorn
LISTEN 0      2048   192.168.56.12:8001      0.0.0.0:*    gunicorn
LISTEN 0      2048   192.168.56.12:8002      0.0.0.0:*    gunicorn
LISTEN 0      4096               *:8025            *:*    mailpit
```

### vm-presentation (192.168.56.11)

```
State  Recv-Q Send-Q Local Address:Port Peer Address:PortProcess                                                  
LISTEN 0      511          0.0.0.0:80        0.0.0.0:*    nginx
```

## Pare-feu (`ufw status`)

### vm-donnees

```
Status: active
To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       192.168.56.1               # SSH depuis WSL
3306/tcp                   ALLOW       192.168.56.12              # MySQL (vm-metier)
6379/tcp                   ALLOW       192.168.56.12              # Redis (vm-metier)
9200/tcp                   ALLOW       192.168.56.12              # Elasticsearch (vm-metier)
2049/tcp                   ALLOW       192.168.56.12              # NFS (vm-metier)
2049/tcp                   ALLOW       192.168.56.11              # NFS lecture seule (vm-presentation)
```

### vm-metier

```
Status: active
To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       192.168.56.1               # SSH depuis WSL
8000:8002/tcp              ALLOW       192.168.56.11              # API (vm-presentation)
8025/tcp on enp0s3         ALLOW       Anywhere                   # Mailpit (redirection de port VirtualBox)
8025/tcp (v6) on enp0s3    ALLOW       Anywhere (v6)              # Mailpit (redirection de port VirtualBox)
```

### vm-presentation

```
Status: active
To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       192.168.56.1               # SSH depuis WSL
80/tcp on enp0s3           ALLOW       Anywhere                   # Site (redirection de port VirtualBox)
80/tcp                     ALLOW       192.168.56.1               # Site (tests depuis WSL)
80/tcp (v6) on enp0s3      ALLOW       Anywhere (v6)              # Site (redirection de port VirtualBox)
```
