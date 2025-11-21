# 🎥 Fluxo Operacional - Monitoramento com Stream de Vídeo

## 📋 Visão Geral

O sistema agora opera com **monitoramento contínuo** via stream de vídeo, onde o **operacional monitora** a entrada e o **sistema identifica automaticamente** as pessoas que passam.

## 👥 Perfis de Usuário

### Operacional
- ✅ Monitora stream de vídeo da entrada
- ✅ Visualiza reconhecimentos em tempo real
- ✅ Cadastra rapidamente pessoas não reconhecidas
- ✅ Gerencia controle de acesso manual
- ✅ Acessa resumos e relatórios

### Admin
- ✅ Todas as permissões do operacional
- ✅ Configura agendamentos
- ✅ Gerencia usuários e permissões
- ✅ Acessa painel administrativo completo

## 🔄 Fluxo Completo do Sistema

### 1. Login do Operacional

```
Operacional acessa o sistema → Faz login → Menu principal
```

### 2. Inicia Monitoramento

```
Menu: "🎥 Monitoramento de Acesso (Stream)"
↓
Sistema carrega modelo de reconhecimento (~2-5 seg)
↓
Operacional clica em "START" para ativar câmera
↓
Stream de vídeo inicia (WebRTC)
```

### 3. Monitoramento Contínuo

#### A) Pessoa Cadastrada (Cenário Ideal)

```
Pessoa passa pela câmera
↓
Sistema detecta rosto (InsightFace)
↓
Sistema compara com banco de dados (~300ms)
↓
🟢 PESSOA RECONHECIDA
↓
Caixa verde aparece com nome da pessoa
↓
Sistema registra acesso automaticamente
├─ Nome
├─ Horário
├─ Empresa
├─ Status: Autorizado
└─ Aprovador: Sistema Automático
↓
Cooldown de 5 segundos (evita duplicatas)
↓
Pessoa pode entrar
```

#### B) Pessoa NÃO Cadastrada

```
Pessoa passa pela câmera
↓
Sistema detecta rosto (InsightFace)
↓
Sistema compara com banco de dados (~300ms)
↓
🔴 PESSOA NÃO RECONHECIDA
↓
Caixa vermelha aparece: "Desconhecido"
↓
Sistema salva frame e embedding
↓
Botão aparece: "📝 Cadastrar Última Pessoa"
↓
OPERACIONAL INTERVÉM:
├─ Clica no botão de cadastro
├─ Visualiza foto capturada
├─ Preenche dados:
│  ├─ Nome Completo *
│  ├─ CPF (opcional)
│  └─ Empresa (opcional)
├─ Clica "✅ Cadastrar e Liberar Acesso"
└─ Sistema:
   ├─ Cria pessoa no banco
   ├─ Salva embedding facial
   ├─ Salva foto no storage
   ├─ Registra acesso automaticamente
   └─ Libera entrada
↓
Pessoa cadastrada para próximas vezes
```

#### C) Pessoa Bloqueada (Lista de Bloqueio)

```
Pessoa passa pela câmera
↓
Sistema detecta e reconhece
↓
🔴 PESSOA BLOQUEADA
↓
Sistema verifica lista de bloqueio
↓
Caixa vermelha: "ACESSO NEGADO"
↓
Sistema registra tentativa de acesso
↓
Operacional é alertado
↓
Operacional impede entrada fisicamente
```

### 4. Ações do Operacional Durante Monitoramento

#### Pausar/Retomar Reconhecimento
```
Botão: "⏸️ Pausar Reconhecimento"
↓
Sistema para de processar frames
↓
Vídeo continua, mas não reconhece
↓
Útil para: limpeza da câmera, ajustes, etc.
```

#### Cadastro Rápido
```
Pessoa não reconhecida aparece
↓
Clica "📝 Cadastrar Última Pessoa"
↓
Preenche formulário
↓
Sistema cadastra e libera automaticamente
```

#### Controle Manual (Se Necessário)
```
Menu: "Controle de Acesso"
↓
Registro manual tradicional
↓
Útil para: problemas técnicos, câmera inativa, etc.
```

## 📊 Interface do Operacional

### Layout da Tela de Monitoramento

```
┌─────────────────────────────────────────────────────────────┐
│  🎥 Monitoramento de Acesso (Vídeo em Tempo Real)          │
│  Sistema Automático - Monitoramento Contínuo                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  [Status]                    [Ações Rápidas]               │
│  ✅ Última pessoa: João      ⏸️ Pausar Reconhecimento      │
│  Horário: 14:35              📝 Cadastrar Última Pessoa    │
│  Empresa: ABC Ltda                                          │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│               [STREAM DE VÍDEO AO VIVO]                     │
│                                                              │
│          ┌──────────────────────────┐                       │
│          │                          │                       │
│          │   🟢 João Silva          │  <- Reconhecido      │
│          │   Similaridade: 92%      │                       │
│          │                          │                       │
│          └──────────────────────────┘                       │
│                                                              │
│                   [START / STOP]                            │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  📊 Estatísticas do Sistema                                 │
│  ┌─────────────┬─────────────┬─────────────┐              │
│  │ Cadastradas │ Total       │ Acessos Hoje│              │
│  │     47      │     52      │     128     │              │
│  └─────────────┴─────────────┴─────────────┘              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## ⚙️ Configurações do Sistema

### Ajustes Recomendados por Cenário

#### Portaria com Fluxo Alto (Muitas Pessoas)

```python
# Em app/face_access_stream.py

# Cooldown menor (reconhece mais rápido)
self.recognition_cooldown = 3  # 3 segundos

# Processa mais frames (mais responsivo)
self.process_every_n_frames = 3  # Processa 1 a cada 3

# Threshold equilibrado
threshold = 0.4  # Padrão
```

#### Portaria com Fluxo Baixo (Poucas Pessoas)

```python
# Cooldown maior (economia de processamento)
self.recognition_cooldown = 10  # 10 segundos

# Processa menos frames (economia de CPU)
self.process_every_n_frames = 10  # Processa 1 a cada 10

# Threshold equilibrado
threshold = 0.4  # Padrão
```

#### Ambiente com Iluminação Variável

```python
# Threshold mais tolerante
threshold = 0.5  # Mais tolerante

# Pode aumentar resolução para melhor captura
"width": {"ideal": 1280},
"height": {"ideal": 720},
```

## 🚨 Situações Especiais

### 1. Câmera Não Disponível
```
Operacional usa: "Controle de Acesso" (manual)
```

### 2. Sistema Lento
```
Operacional ajusta:
- Reduz resolução (640x480)
- Aumenta process_every_n_frames (10)
```

### 3. Muitos Falsos Positivos
```
Admin ajusta:
- Reduz threshold (0.3)
- Recadastra pessoas com fotos melhores
```

### 4. Muitos Falsos Negativos
```
Admin ajusta:
- Aumenta threshold (0.5)
- Melhora iluminação da entrada
```

## 📝 Procedimentos Operacionais Padrão (POP)

### Início do Turno

1. ✅ Fazer login no sistema
2. ✅ Acessar "🎥 Monitoramento de Acesso"
3. ✅ Aguardar carregamento do modelo (~5 seg)
4. ✅ Clicar em "START" para ativar câmera
5. ✅ Verificar que o vídeo está ativo
6. ✅ Testar reconhecimento (passar pela câmera)
7. ✅ Verificar estatísticas do dia

### Durante o Turno

#### Para cada pessoa que entra:

1. 👁️ **Monitore o stream**
   - Aguarde pessoa aparecer no vídeo
   
2. 🟢 **Se caixa verde (reconhecido):**
   - Libere entrada
   - Sistema registra automaticamente
   
3. 🔴 **Se caixa vermelha (não reconhecido):**
   - Aborde a pessoa
   - Solicite identificação
   - Clique "📝 Cadastrar Última Pessoa"
   - Preencha dados
   - Clique "✅ Cadastrar e Liberar Acesso"
   - Libere entrada
   
4. 🚫 **Se pessoa bloqueada:**
   - Sistema alertará (caixa vermelha)
   - NÃO libere entrada
   - Chame supervisor/segurança

### Fim do Turno

1. ✅ Verificar estatísticas do dia
2. ✅ Pausar reconhecimento (⏸️)
3. ✅ Fazer logout
4. ✅ Repassar para próximo turno

## 📊 Métricas de Desempenho

### Métricas Esperadas

| Métrica | Objetivo | Aceitável | Crítico |
|---------|----------|-----------|---------|
| Taxa de reconhecimento | >95% | >90% | <85% |
| Falsos positivos | <2% | <5% | >10% |
| Falsos negativos | <3% | <7% | >15% |
| Tempo de reconhecimento | <500ms | <1s | >2s |
| Disponibilidade do sistema | >99% | >95% | <90% |

### Ações Corretivas

#### Taxa de reconhecimento baixa (<90%)
- Verificar iluminação
- Limpar lente da câmera
- Recadastrar pessoas
- Ajustar threshold

#### Muitos falsos positivos (>5%)
- Reduzir threshold (0.3)
- Recadastrar pessoas
- Melhorar qualidade das fotos

#### Tempo de reconhecimento alto (>1s)
- Verificar carga do servidor
- Aumentar process_every_n_frames
- Reduzir resolução da câmera

## 🎯 Melhores Práticas

### Para Operadores

1. ✅ **Sempre monitore ativamente** - não deixe o sistema sozinho
2. ✅ **Cadastre rapidamente** - use o botão de cadastro rápido
3. ✅ **Oriente visitantes** - peça para olhar para câmera
4. ✅ **Mantenha câmera limpa** - limpe lente regularmente
5. ✅ **Reporte problemas** - informe admin sobre falhas

### Para Administradores

1. ✅ **Monitore métricas** - verifique estatísticas semanalmente
2. ✅ **Ajuste configurações** - otimize conforme necessidade
3. ✅ **Treine operadores** - garanta que sabem usar o sistema
4. ✅ **Mantenha cadastros** - recadastre fotos antigas
5. ✅ **Teste regularmente** - valide reconhecimento periodicamente

## 🔐 Segurança e Privacidade

### Dados Coletados

- ✅ **Foto facial:** Armazenada no Supabase Storage
- ✅ **Embedding facial:** Vetor numérico (512 dimensões)
- ✅ **Dados pessoais:** Nome, CPF (opcional), Empresa
- ✅ **Registros de acesso:** Data, hora, status

### Conformidade LGPD

- ✅ **Consentimento:** Obtido no momento do cadastro
- ✅ **Finalidade:** Controle de acesso e segurança
- ✅ **Minimização:** Apenas dados necessários
- ✅ **Segurança:** Criptografia em trânsito e repouso
- ✅ **Retenção:** Conforme política da empresa

### Direitos dos Titulares

- ✅ **Acesso:** Podem solicitar seus dados
- ✅ **Correção:** Podem atualizar informações
- ✅ **Exclusão:** Podem solicitar remoção
- ✅ **Portabilidade:** Podem exportar dados

## 📞 Suporte

### Em caso de problemas:

1. **Técnicos:** Cristian Ferreira Carlos
   - Email: cristiancarlos@vibraenergia.com.br
   - Tel: +55 11 3103-8708

2. **Operacionais:** Supervisor do turno

3. **Urgências:** Seguir protocolo de segurança da empresa

---

**Versão:** 2.0 (Stream Operacional)  
**Última Atualização:** 21/11/2025  
**Desenvolvido por:** Cristian Ferreira Carlos

