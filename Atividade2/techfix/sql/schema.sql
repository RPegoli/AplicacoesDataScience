-- =====================================================================
-- TechFix Informática — Sistema de Ordens de Serviço
-- Script de criação do banco (Supabase / PostgreSQL)
-- Execute este arquivo inteiro no SQL Editor do Supabase.
-- O script é idempotente: pode ser rodado novamente sem erro.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 0. Limpeza (opcional)
-- Remove as tabelas caso já existam, para recriar do zero.
-- ATENÇÃO: apaga todos os dados. Comente estas linhas se não quiser isso.
-- ---------------------------------------------------------------------
drop table if exists public.ordens_servico cascade;
drop table if exists public.clientes cascade;
drop function if exists public.atualiza_data_atualizacao() cascade;


-- ---------------------------------------------------------------------
-- 1. Tabela CLIENTES
-- Um cliente é identificado de forma única pelo e-mail.
-- O mesmo cliente pode abrir várias ordens de serviço ao longo do tempo.
-- ---------------------------------------------------------------------
create table public.clientes (
    -- Chave primária gerada automaticamente pelo banco
    id                bigint generated always as identity primary key,

    nome              text        not null,
    endereco          text        not null,

    -- E-mail único; guardado sempre em minúsculas para evitar duplicatas
    -- do tipo "Ana@x.com" x "ana@x.com"
    email             text        not null unique,

    -- Celular/WhatsApp: somente dígitos (DDD + número, opcionalmente com DDI)
    celular_whatsapp  text        not null,

    -- Data de cadastro preenchida automaticamente
    data_cadastro     timestamptz not null default now(),

    -- Restrições de integridade (validações simples no próprio banco)
    constraint ck_clientes_nome_nao_vazio
        check (length(trim(nome)) > 0),
    constraint ck_clientes_endereco_nao_vazio
        check (length(trim(endereco)) > 0),
    constraint ck_clientes_email_formato
        check (email ~* '^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$'),
    constraint ck_clientes_email_minusculo
        check (email = lower(email)),
    constraint ck_clientes_celular_formato
        check (celular_whatsapp ~ '^[0-9]{10,13}$')
);

comment on table  public.clientes                  is 'Clientes da TechFix Informática';
comment on column public.clientes.celular_whatsapp is 'Somente dígitos, 10 a 13 caracteres (ex.: 11987654321)';


-- ---------------------------------------------------------------------
-- 2. Tabela ORDENS_SERVICO
-- Cada OS pertence a um cliente (chave estrangeira).
-- ON DELETE CASCADE: ao excluir um cliente, as OS dele também são
-- excluídas (o painel Streamlit avisa isso antes de confirmar).
-- ---------------------------------------------------------------------
create table public.ordens_servico (
    id                 bigint generated always as identity primary key,

    cliente_id         bigint      not null
        references public.clientes (id)
        on update cascade
        on delete cascade,

    modelo_computador  text        not null,
    problema_relatado  text        not null,

    -- Status do atendimento; toda OS nasce como 'Aberto'
    status             text        not null default 'Aberto',

    data_abertura      timestamptz not null default now(),
    data_atualizacao   timestamptz not null default now(),

    -- Apenas os status do fluxo de atendimento são aceitos
    constraint ck_os_status
        check (status in ('Aberto', 'Em análise', 'Aguardando peça', 'Concluído', 'Entregue')),
    constraint ck_os_modelo_nao_vazio
        check (length(trim(modelo_computador)) > 0),
    constraint ck_os_problema_nao_vazio
        check (length(trim(problema_relatado)) > 0)
);

comment on table  public.ordens_servico        is 'Ordens de serviço (equipamentos deixados para reparo)';
comment on column public.ordens_servico.status is 'Aberto → Em análise → Aguardando peça → Concluído → Entregue';


-- ---------------------------------------------------------------------
-- 3. Índices
-- Aceleram as consultas mais comuns do painel (filtro por status e
-- junção OS → cliente). O e-mail já tem índice por causa do UNIQUE.
-- ---------------------------------------------------------------------
create index idx_os_cliente_id    on public.ordens_servico (cliente_id);
create index idx_os_status        on public.ordens_servico (status);
create index idx_os_data_abertura on public.ordens_servico (data_abertura desc);


-- ---------------------------------------------------------------------
-- 4. Trigger de data_atualizacao
-- Sempre que uma OS for alterada, o banco grava a data/hora da alteração
-- automaticamente (a aplicação não precisa se preocupar com isso).
-- ---------------------------------------------------------------------
create or replace function public.atualiza_data_atualizacao()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.data_atualizacao := now();
    return new;
end;
$$;

create trigger trg_os_data_atualizacao
    before update on public.ordens_servico
    for each row
    execute function public.atualiza_data_atualizacao();


-- ---------------------------------------------------------------------
-- 5. Segurança: Row Level Security (RLS) e políticas de acesso
-- O Supabase expõe as tabelas pela API REST. Com RLS ligado, nada é
-- acessível sem uma política explícita.
--
-- Como esta é uma atividade acadêmica sem login de usuários, as políticas
-- abaixo liberam leitura/escrita para a chave "anon" usada pelos apps.
-- Em produção, troque "anon" por "authenticated" e exija login.
-- A chave service_role NUNCA deve ser usada nos apps nem publicada.
-- ---------------------------------------------------------------------
alter table public.clientes       enable row level security;
alter table public.ordens_servico enable row level security;

create policy "clientes_select" on public.clientes       for select to anon, authenticated using (true);
create policy "clientes_insert" on public.clientes       for insert to anon, authenticated with check (true);
create policy "clientes_update" on public.clientes       for update to anon, authenticated using (true) with check (true);
create policy "clientes_delete" on public.clientes       for delete to anon, authenticated using (true);

create policy "os_select"       on public.ordens_servico for select to anon, authenticated using (true);
create policy "os_insert"       on public.ordens_servico for insert to anon, authenticated with check (true);
create policy "os_update"       on public.ordens_servico for update to anon, authenticated using (true) with check (true);
create policy "os_delete"       on public.ordens_servico for delete to anon, authenticated using (true);


-- ---------------------------------------------------------------------
-- 6. Dados de teste (100% fictícios — LGPD)
-- E-mails no domínio reservado example.com e celulares inventados.
-- ---------------------------------------------------------------------
insert into public.clientes (nome, endereco, email, celular_whatsapp) values
    ('Ana Teste da Silva',   'Rua das Flores, 100 - Centro',      'ana.teste@example.com',    '11900000001'),
    ('Bruno Exemplo Souza',  'Av. Brasil, 2500 - Jardim América', 'bruno.exemplo@example.com', '21900000002'),
    ('Carla Fictícia Lima',  'Rua Sete, 77 - Vila Nova',          'carla.ficticia@example.com','31900000003');

insert into public.ordens_servico (cliente_id, modelo_computador, problema_relatado, status) values
    (1, 'Notebook Dell Inspiron 15',  'Não liga, LED de energia pisca laranja.',        'Aberto'),
    (1, 'Impressora HP DeskJet 2774', 'Papel enrosca na saída.',                         'Concluído'),
    (2, 'Desktop montado Ryzen 5',    'Reinicia sozinho durante jogos.',                 'Em análise'),
    (3, 'MacBook Air M1',             'Tela com listras verticais após queda.',          'Aguardando peça'),
    (3, 'Mouse Logitech G203',        'Clique duplo involuntário no botão esquerdo.',    'Entregue');


-- ---------------------------------------------------------------------
-- 7. Testes das restrições (descomente para conferir — devem FALHAR)
-- ---------------------------------------------------------------------
-- insert into public.clientes (nome, endereco, email, celular_whatsapp)
--     values ('X', 'Y', 'email-invalido', '11900000009');          -- e-mail inválido
-- insert into public.clientes (nome, endereco, email, celular_whatsapp)
--     values ('X', 'Y', 'ana.teste@example.com', '11900000009');   -- e-mail duplicado
-- insert into public.clientes (nome, endereco, email, celular_whatsapp)
--     values ('X', 'Y', 'x@example.com', '(11) 9000-0000');        -- celular com símbolos
-- insert into public.ordens_servico (cliente_id, modelo_computador, problema_relatado, status)
--     values (1, 'PC', 'Teste', 'Pronto');                          -- status inválido
-- insert into public.ordens_servico (cliente_id, modelo_computador, problema_relatado)
--     values (999, 'PC', 'Teste');                                  -- cliente inexistente (FK)
