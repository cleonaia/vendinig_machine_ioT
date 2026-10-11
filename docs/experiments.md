# Experimentos

Ejecuta desde la raíz para comparar el mismo escenario con controles activos y desactivados:

```sh
python -m scenarios.run_all --scenario chain --profile hardened
python -m scenarios.run_all --scenario chain --profile vulnerable
python -m scenarios.run_all --scenario replay --profile vulnerable --json
```

Registra el perfil, escenario, `objective_achieved`, intentos y eventos. La salida es determinista, así que las diferencias se deben a la configuración de controles y no a azar. En perfil vulnerable, la repetición puede dispensar dos veces y la manipulación puede superar verificaciones que se hayan desactivado; esto solo demuestra el comportamiento del modelo local.

Para una práctica, cambia un control cada vez en `scenarios/lab.py` y observa qué escenarios pasan. No uses resultados como evidencia sobre máquinas reales.
