#!/bin/bash
# Arranca Jupyter Notebook dentro del contenedor para análisis con pandas.
# Uso (desde el host):
#   docker exec -u django -ti django_app_debug_termostato_django /srv/project/run_jupyter.sh
#
# Para que Django esté disponible en los notebooks, ejecuta primero una vez:
#   docker exec -u django -ti django_app_debug_termostato_django \
#     python3 /srv/project/manage.py shell_plus --kernel

echo "*************************************"
echo "*    Starting Jupyter Notebook      *"
echo "*************************************"

echo "port: ${EXPOSE_PUBLIC_PORT_DJANGO_JUPYTER:-3336}"

jupyter notebook \
  --ip=0.0.0.0 \
  --port="${EXPOSE_PUBLIC_PORT_DJANGO_JUPYTER:-3336}" \
  --no-browser \
  --NotebookApp.allow_remote_access=True \
  --NotebookApp.token='' \
  --allow-root \
  --notebook-dir=/srv/project/jupyter_notebooks
