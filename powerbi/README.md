# Informe Power BI

Abrir `Turismo.pbip` en una versión actual de Power BI Desktop para Windows. Autorizar acceso **anónimo** a `https://raw.githubusercontent.com`, actualizar las consultas y seleccionar un año en cada página. Los CSV son públicos y no contienen información personal.

## Páginas

1. Resumen: indicadores, evolución mensual y distribución provincial.
2. Territorio: viajeros, noches, ocupación ponderada, variación y viviendas.
3. Mercados: gasto anual por país y gasto regional mensual, sin desglose provincial.
4. Previsión: seis meses futuros, límites orientativos y modelo por provincia. Seleccionar el año futuro correspondiente para ver esos meses.

Modelo: cinco tablas de hechos y tres dimensiones. `dim_year` filtra el calendario y el hecho anual; el calendario filtra los hechos mensuales y semestrales. Las relaciones provinciales solo llegan a hoteles, viviendas y previsiones. No se unen países a provincias.

La ocupación se pondera por plazas disponibles y días del mes. La estancia es la razón entre noches y viajeros. El interanual desplaza únicamente los meses observados. La cuota extranjera queda vacía si falta alguna observación. La medida de viviendas toma la última observación visible, sin sumar snapshots.

## Seguridad

Ocho roles fijos, uno por provincia. Filtran `dim_province` y, mediante sus relaciones, hoteles, viviendas y previsiones. Los hechos regionales se deniegan con `FALSE()` para esos roles; su acceso debe concederse por separado a usuarios regionales. Los roles no contienen usuarios ni correos.

En Desktop: **Modelado → Ver como** cada rol. Comprobar que solo aparece su provincia y que las visualizaciones regionales quedan vacías. En el servicio, asignar un único rol provincial a cada lector: varias pertenencias se combinan de forma aditiva. Los administradores del workspace no representan una prueba de RLS.

## Validación reproducible

```sh
dotnet run --project tools/ValidateSemanticModel -- powerbi/Turismo.SemanticModel/definition
uv run python tools/validate_pbir.py
```

TOM deserializa el modelo y comprueba sus dimensiones, relaciones, referencias y filtros. La validación PBIR utiliza copias de los esquemas oficiales, conservadas en `tools/pbir-schemas`. Son comprobaciones estructurales: no ejecutan DAX, no procesan el modelo ni certifican la representación visual. La apertura, actualización, medidas y roles en el motor de Power BI quedan pendientes de un entorno Windows. No se incluyen capturas simuladas.

Documentación original: [PBIP](https://learn.microsoft.com/power-bi/developer/projects/projects-overview), [PBIR](https://learn.microsoft.com/power-bi/developer/projects/projects-report), [TMDL](https://learn.microsoft.com/analysis-services/tmdl/tmdl-overview).
