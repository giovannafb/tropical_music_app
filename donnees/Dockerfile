FROM mysql:8.4

# Configuration utf8mb4 copiée dans l'image (et non montée) : MySQL ignore un fichier de
# configuration modifiable par tous, ce qui est le cas d'un fichier monté depuis Windows.
COPY mysql/conf.d/musicapp.cnf /etc/mysql/conf.d/musicapp.cnf
RUN chmod 644 /etc/mysql/conf.d/musicapp.cnf
