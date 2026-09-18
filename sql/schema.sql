-- Ejecutar en Supabase > SQL Editor

CREATE TABLE IF NOT EXISTS contribuyentes (
    id SERIAL PRIMARY KEY,
    rif VARCHAR(20) UNIQUE NOT NULL,
    razon_social VARCHAR(200) NOT NULL,
    direccion TEXT
);

CREATE TABLE IF NOT EXISTS declaraciones (
    id SERIAL PRIMARY KEY,
    contribuyente_id INTEGER NOT NULL REFERENCES contribuyentes(id),
    periodo VARCHAR(20) NOT NULL,
    ingresos_declarados NUMERIC(14,2) NOT NULL,
    ingresos_reales NUMERIC(14,2) NOT NULL,
    diferencia NUMERIC(14,2),
    impuesto_omitido NUMERIC(14,2),
    recargo NUMERIC(14,2),
    reparo_fiscal NUMERIC(14,2),
    fecha_registro TIMESTAMP DEFAULT NOW()
);
