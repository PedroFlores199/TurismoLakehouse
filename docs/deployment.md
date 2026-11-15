# Despliegue y limpieza

## Local, sin cuenta

`docker compose up --build -d web` sirve la captura de datos incluida. El perfil `etl` ejecuta Spark/Delta con Java 21. `docker compose down` detiene el panel; `docker compose down -v` elimina también el volumen del lake creado por este proyecto.

## Azure preparado

Requisitos: suscripción Azure, permisos para crear recursos y asignar roles, CLI de Azure, Terraform, acceso administrador a la cuenta/workspace Databricks y dos grupos ya creados en Databricks (`engineers_group`, `readers_group`). Revisar [costs.md](costs.md) antes de continuar.

1. Autenticarse en Azure y Databricks con el método admitido por los proveedores de Terraform. Confirmar suscripción y tenant; no guardar credenciales en archivos del repositorio.
2. Crear `infra/local.tfvars` con `subscription_id`, nombres de los dos grupos y `existing_metastore_id` si la región ya tiene un metastore. En cuentas con asignación automática, usar ese metastore. `allow_billable_resources=true` solo tras decidir activar recursos; mantener `enable_monthly_trigger=false` para la primera prueba.
3. Ejecutar `terraform -chdir=infra init`, `terraform -chdir=infra validate` y `terraform -chdir=infra plan -var-file=local.tfvars`. Revisar el plan completo antes de `apply`.
4. El proveedor Databricks necesita alcanzar el workspace creado durante el despliegue. En una suscripción nueva puede ser necesario aplicar primero la capa Azure y completar después la configuración del workspace; no usar planes con recursos aún desconocidos como prueba de funcionamiento.
5. En ADF, lanzar `TurismoMetadataIngest`. La lista de fuentes se lee de ADLS; cada REST copy deja JSON en `landing/raw/<tabla>.json`. El notebook consume ese volumen, normaliza y hace MERGE en `turismo.bronze/silver/gold`. Revisar los siete controles antes de conectar lectores.
6. Comprobar en Unity Catalog las identidades, grupos y grants; probar lectura Gold con un lector sin privilegios de ingeniería. No mezclar permisos administrativos con la prueba del lector.

El bundle en `databricks/` permite ejecutar el mismo paquete como job. Desde esa carpeta: `databricks bundle validate -t dev` y `databricks bundle deploy -t dev` después de configurar la autenticación. El job usa un driver y un worker D4ds v5, runtime 17.3 y un timeout de una hora. La infraestructura y la configuración se validan estáticamente; la ejecución cloud no se ha probado sin una cuenta y suscripción.

## AEMET

`tourism/weather.py` contiene un cliente con clave enviada en cabecera y ventanas de catorce días. No incluye claves. Seleccionar estaciones y definir la agregación territorial antes de integrar esa fuente; la demo no publica clima sin descargarlo.

## Limpieza cloud

Desactivar primero el trigger y comprobar que no haya jobs activos. Ejecutar `terraform -chdir=infra plan -destroy -var-file=local.tfvars` y revisar los recursos de este proyecto; después `terraform -chdir=infra destroy -var-file=local.tfvars`. Verificar en Azure los grupos de recursos normal y administrado, y en Databricks los jobs, catálogo y credenciales de almacenamiento. El metastore compartido aportado por `existing_metastore_id` no debe eliminarse. Key Vault conserva elementos borrados durante su período de recuperación. Revisar Cost Management después de la limpieza.

No se ha aplicado, destruido ni modificado ningún recurso cloud durante las pruebas locales.
