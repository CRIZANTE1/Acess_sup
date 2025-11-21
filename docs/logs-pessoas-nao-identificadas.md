# 📋 Logs de Pessoas Não Identificadas

## ✅ Implementação Concluída

Sistema agora registra **automaticamente** todos os eventos relacionados a pessoas não identificadas.

---

## 🎯 Eventos Registrados

### 1. **UNKNOWN_PERSON_DETECTED**
- **Quando:** Pessoa não identificada é detectada no stream (sistema com login)
- **Detalhes:** Data, hora e nível de confiança da detecção
- **Frequência:** Uma vez por detecção (evita duplicatas)
- **Local:** Página "Monitoramento de Acesso (Stream)"

```
Exemplo de log:
Action: UNKNOWN_PERSON_DETECTED
Details: Pessoa não identificada detectada no stream em 21/11/2025 14:30:45 (Confidence: 0.92)
User: SISTEMA
```

### 2. **UNKNOWN_PERSON_DETECTED_PUBLIC**
- **Quando:** Pessoa não identificada é detectada no acesso público
- **Detalhes:** Data, hora e nível de confiança da detecção
- **Frequência:** A cada 30 segundos (evita spam)
- **Local:** Página de acesso público (sem login)

```
Exemplo de log:
Action: UNKNOWN_PERSON_DETECTED_PUBLIC
Details: Pessoa não identificada detectada no acesso público em 21/11/2025 14:30:45 (Confidence: 0.89)
User: SISTEMA
```

### 3. **UNKNOWN_PERSON_IGNORED**
- **Quando:** Operador clica em "Ignorar" ao ver pessoa não identificada
- **Detalhes:** Data e hora da ação
- **User:** Usuário logado
- **Local:** Popup de pessoa não reconhecida

```
Exemplo de log:
Action: UNKNOWN_PERSON_IGNORED
Details: Pessoa não identificada foi ignorada pelo operador em 21/11/2025 14:31:00
User: operador@baeri.com.br
```

### 4. **UNKNOWN_PERSON_REGISTERED**
- **Quando:** Operador cadastra a pessoa não identificada
- **Detalhes:** Nome e ID da pessoa cadastrada
- **User:** SISTEMA (complementa o log do usuário)
- **Local:** Formulário de cadastro rápido

```
Exemplo de log:
Action: UNKNOWN_PERSON_REGISTERED
Details: Pessoa não identificada foi cadastrada como 'João Silva' (ID: 123) pelo operador
User: SISTEMA
```

### 5. **FACE_STREAM_QUICK_REGISTER**
- **Quando:** Cadastro rápido é concluído
- **Detalhes:** Nome e ID da pessoa
- **User:** Usuário que fez o cadastro
- **Local:** Formulário de cadastro rápido

```
Exemplo de log:
Action: FACE_STREAM_QUICK_REGISTER
Details: Cadastro rápido via stream: 'João Silva' (ID: 123)
User: operador@baeri.com.br
```

---

## 📊 Como Visualizar os Logs

### No Sistema
1. Faça login como **administrador**
2. Vá para **"Painel Administrativo"**
3. Clique na aba **"Logs"**
4. Filtre por:
   - `UNKNOWN_PERSON_*` para ver todas as detecções
   - `UNKNOWN_PERSON_DETECTED` para ver apenas detecções no stream
   - `UNKNOWN_PERSON_IGNORED` para ver pessoas ignoradas
   - `UNKNOWN_PERSON_REGISTERED` para ver cadastros

### Ordenação
- Logs aparecem ordenados do **mais recente** para o mais antigo
- Mostra: Timestamp, Usuário, Ação e Detalhes

---

## 🔍 Análise de Logs

### Identificar Padrões
```sql
-- Quantidade de pessoas não identificadas por dia
SELECT 
    DATE(timestamp) as data,
    COUNT(*) as total_deteccoes
FROM logs
WHERE action LIKE 'UNKNOWN_PERSON_DETECTED%'
GROUP BY DATE(timestamp)
ORDER BY data DESC;
```

### Monitorar Taxa de Cadastro
```sql
-- Taxa de conversão: detecções → cadastros
SELECT 
    (SELECT COUNT(*) FROM logs WHERE action = 'UNKNOWN_PERSON_REGISTERED') as cadastros,
    (SELECT COUNT(*) FROM logs WHERE action LIKE 'UNKNOWN_PERSON_DETECTED%') as deteccoes,
    ROUND(
        (SELECT COUNT(*) FROM logs WHERE action = 'UNKNOWN_PERSON_REGISTERED') * 100.0 / 
        NULLIF((SELECT COUNT(*) FROM logs WHERE action LIKE 'UNKNOWN_PERSON_DETECTED%'), 0)
    , 2) as taxa_conversao_percentual;
```

### Horários de Maior Incidência
```sql
-- Horários com mais pessoas não identificadas
SELECT 
    HOUR(timestamp) as hora,
    COUNT(*) as total
FROM logs
WHERE action LIKE 'UNKNOWN_PERSON_DETECTED%'
GROUP BY HOUR(timestamp)
ORDER BY total DESC
LIMIT 10;
```

---

## 🛠️ Arquivos Modificados

### 1. `app/logger.py`
- ✅ Adicionada função `log_system_action()` para logs sem usuário logado
- ✅ Logs do sistema usam "SISTEMA" como user quando não há login

### 2. `app/face_access_stream.py`
- ✅ Importa `log_system_action`
- ✅ Log ao detectar pessoa não identificada (linha ~335)
- ✅ Log ao ignorar pessoa não identificada (linha ~165)
- ✅ Log ao cadastrar pessoa não identificada (linha ~530)

### 3. `app/public_face_access_stream.py`
- ✅ Importa `log_system_action`
- ✅ Log ao detectar pessoa não identificada no acesso público (linha ~168)
- ✅ Cooldown de 30 segundos para evitar spam de logs

---

## ⚙️ Configurações

### Cooldown de Logs
- **Stream (com login):** 1 log por detecção (popup)
- **Acesso público:** 1 log a cada 30 segundos (evita spam)

### Nível de Confiança Registrado
- Todos os logs incluem o `Confidence` da detecção facial
- Útil para análise de qualidade do reconhecimento

---

## 📈 Métricas Úteis

### Monitoramento de Segurança
- Quantidade de pessoas não identificadas por turno
- Locais/horários com maior incidência
- Taxa de resposta da equipe (ignorar vs cadastrar)

### Melhoria do Sistema
- Analisar confiança das detecções
- Identificar falsos positivos
- Otimizar threshold de reconhecimento

### Compliance
- Rastreamento completo de todas as detecções
- Auditoria de ações dos operadores
- Histórico de cadastros rápidos

---

## 🎯 Próximos Passos Recomendados

1. **Dashboard de Análise**
   - Criar visualizações dos logs de pessoas não identificadas
   - Gráficos de tendências e horários de pico

2. **Alertas Automáticos**
   - Notificar administradores após X detecções não resolvidas
   - Alertar sobre padrões anormais

3. **Exportação de Relatórios**
   - Relatório mensal de pessoas não identificadas
   - Análise de eficiência do sistema

---

## 💡 Dicas

- ✅ Revise os logs semanalmente para identificar padrões
- ✅ Treine operadores a sempre cadastrar ou ignorar (não deixar pendente)
- ✅ Monitore a taxa de conversão (detecção → cadastro)
- ✅ Ajuste o threshold se houver muitos falsos positivos

---

**Última atualização:** 21/11/2025
**Versão:** 2.0 - Sistema de Logs Completo

