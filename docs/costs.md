# Costes antes de activar Azure

La demo local cuesta **0 € en servicios cloud**. No se ha ejecutado `terraform apply` ni contratado servicios. Este documento no autoriza cargos.

Ejemplo orientativo para West Europe, USD sin impuestos, precios públicos consultados el 15/11/2026:

| Concepto | Hipótesis |
|---|---|
| Jobs Compute Premium | 0,30 USD por DBU/h |
| VM Linux D4ds v5 | 0,272 USD por nodo/h |
| Ejecución | Un driver y un worker, dos horas cada uno |
| Consumo DBU | Escenario de 0,75–1 DBU por nodo/h; confirmar el valor aplicable en el calculador |

Cómputo del ejemplo: `2 nodos × 2 h × (0,272 + 0,30 × [0,75–1])` = **1,988–2,288 USD por ejecución**. Es una estimación de cómputo, no una factura ni un presupuesto completo. ADF (actividades y movimiento), almacenamiento, operaciones ADLS/Key Vault, tráfico, logs y licencias Power BI se añaden. La tarifa real depende de región, moneda, contrato, disponibilidad y tiempo de arranque. Dejar recursos o clusters activos cambia el coste.

Comprobar antes de activar: [precios Azure Databricks](https://azure.microsoft.com/pricing/details/databricks/), [calculadora Azure](https://azure.microsoft.com/pricing/calculator/), [Retail Prices API](https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices). Configurar un presupuesto y una alerta; una alerta no detiene el gasto automáticamente.

La variable `allow_billable_resources` exige activación explícita y `enable_monthly_trigger=false` evita la programación periódica. Ejecutar la limpieza descrita en [deployment.md](deployment.md) al terminar.
