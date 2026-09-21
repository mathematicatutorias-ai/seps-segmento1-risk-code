# Indicadores
Fórmulas y vigencias en YAML; fuente metodológica SEPS.

## Update 011 · Dependencias entre indicadores derivados
Las features se evalúan en el orden declarado en `config/features.yaml`. Cada resultado derivado se incorpora al entorno de evaluación antes de calcular la siguiente feature. Esto permite dependencias explícitas como:

`loan_portfolio_net` + `loan_provisions` → `loan_portfolio_gross` → `delinquency_ratio`.

Ningún error de evaluación puede omitirse silenciosamente. Una expresión inválida debe detener el cálculo con el nombre de la feature, fórmula y causa.
