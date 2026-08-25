--
-- PostgreSQL database dump
--

\restrict olC8FSwCxYbbqHpWFlyoIbSlcZZJnnj4VfJeJ9ciNbilOjIjCv5qi4g46Ys0aU0

-- Dumped from database version 15.19 (Debian 15.19-1.pgdg13+2)
-- Dumped by pg_dump version 15.19 (Debian 15.19-1.pgdg13+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: shb_prepare_approval(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.shb_prepare_approval() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
          IF NEW.idempotency_key IS NULL OR NEW.idempotency_key='' THEN
            NEW.idempotency_key := 'idem:v1:' || NEW.conv_id || ':' || NEW.action || ':' || NEW.payload_hash;
          END IF;
          IF TG_OP='INSERT' THEN
            NEW.created_at := COALESCE(NEW.created_at,now());
            NEW.updated_at := COALESCE(NEW.updated_at,NEW.created_at);
            NEW.row_version := COALESCE(NEW.row_version,0);
          ELSE
            NEW.updated_at := now();
            NEW.row_version := OLD.row_version + 1;
          END IF;
          RETURN NEW;
        END $$;


--
-- Name: shb_refresh_party_references(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.shb_refresh_party_references(p_owner_id text) RETURNS void
    LANGUAGE plpgsql
    AS $$
        BEGIN
          UPDATE users SET party_id=p_owner_id WHERE owner_id=p_owner_id;
          UPDATE loans SET party_id=p_owner_id WHERE owner_id=p_owner_id;
          UPDATE cic_records SET party_id=p_owner_id WHERE owner_id=p_owner_id;
          UPDATE collaterals SET party_id=p_owner_id WHERE owner_id=p_owner_id;
          UPDATE owner_documents SET party_id=p_owner_id WHERE owner_id=p_owner_id;
          UPDATE police_records SET party_id=p_owner_id WHERE owner_id=p_owner_id;
          UPDATE employment_records SET party_id=p_owner_id WHERE owner_id=p_owner_id;
          UPDATE assessments SET party_id=p_owner_id WHERE owner_id=p_owner_id;
          UPDATE applications SET party_id=p_owner_id WHERE owner_id=p_owner_id;
          UPDATE interaction_notes SET party_id=p_owner_id WHERE owner_id=p_owner_id;
          UPDATE party_relations SET from_party_id=p_owner_id WHERE from_id=p_owner_id;
          UPDATE party_relations SET to_party_id=p_owner_id WHERE to_id=p_owner_id;
        END $$;


--
-- Name: shb_reject_consent_mutation(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.shb_reject_consent_mutation() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
          RAISE EXCEPTION 'consent_records is append-only' USING ERRCODE='55000';
        END $$;


--
-- Name: shb_reject_tenant_change(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.shb_reject_tenant_change() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
          IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id THEN
            RAISE EXCEPTION 'tenant_id is immutable for %', TG_TABLE_NAME
              USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$;


--
-- Name: shb_resolve_conversation_reference(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.shb_resolve_conversation_reference() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        DECLARE resolved_id uuid; resolved_tenant uuid;
        BEGIN
          SELECT id, tenant_id INTO resolved_id, resolved_tenant
          FROM conversations WHERE id::text=NEW.conv_id;
          IF FOUND THEN
            NEW.conversation_id := resolved_id;
            NEW.tenant_id := resolved_tenant;
          ELSIF NEW.tenant_id IS NULL THEN
            NEW.tenant_id := '00000000-0000-0000-0000-000000000001'::uuid;
          END IF;
          RETURN NEW;
        END $$;


--
-- Name: shb_resolve_party_reference(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.shb_resolve_party_reference() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
          NEW.party_id := (SELECT owner_id FROM parties WHERE owner_id=NEW.owner_id);
          RETURN NEW;
        END $$;


--
-- Name: shb_resolve_relation_parties(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.shb_resolve_relation_parties() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
          NEW.from_party_id := (SELECT owner_id FROM parties WHERE owner_id=NEW.from_id);
          NEW.to_party_id := (SELECT owner_id FROM parties WHERE owner_id=NEW.to_id);
          RETURN NEW;
        END $$;


--
-- Name: shb_sync_approval_attempt_tenant(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.shb_sync_approval_attempt_tenant() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        DECLARE resolved_tenant uuid;
        BEGIN
          SELECT tenant_id INTO resolved_tenant FROM approvals WHERE id=NEW.approval_id;
          IF FOUND THEN
            NEW.tenant_id := resolved_tenant;
          ELSIF NEW.tenant_id IS NULL THEN
            NEW.tenant_id := '00000000-0000-0000-0000-000000000001'::uuid;
          END IF;
          RETURN NEW;
        END $$;


--
-- Name: shb_sync_business_party(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.shb_sync_business_party() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
          INSERT INTO parties(owner_id,party_type,display_name)
          VALUES(NEW.id,'business',NEW.name)
          ON CONFLICT(owner_id) DO UPDATE
            SET display_name=EXCLUDED.display_name, updated_at=now()
            WHERE parties.party_type='business';
          IF NOT FOUND THEN RAISE EXCEPTION 'owner_id is already assigned to another party type'; END IF;
          PERFORM shb_refresh_party_references(NEW.id);
          RETURN NEW;
        END $$;


--
-- Name: shb_sync_customer_party(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.shb_sync_customer_party() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
          INSERT INTO parties(owner_id,party_type,display_name)
          VALUES(NEW.id,'customer',NEW.full_name)
          ON CONFLICT(owner_id) DO UPDATE
            SET display_name=EXCLUDED.display_name, updated_at=now()
            WHERE parties.party_type='customer';
          IF NOT FOUND THEN RAISE EXCEPTION 'owner_id is already assigned to another party type'; END IF;
          PERFORM shb_refresh_party_references(NEW.id);
          RETURN NEW;
        END $$;


--
-- Name: shb_sync_task_attempt_tenant(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.shb_sync_task_attempt_tenant() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        DECLARE resolved_tenant uuid; resolved_conversation uuid;
        BEGIN
          SELECT tenant_id, conversation_id INTO resolved_tenant, resolved_conversation
          FROM tasks WHERE id=NEW.task_id;
          IF FOUND THEN
            NEW.tenant_id := resolved_tenant;
            NEW.conversation_id := COALESCE(NEW.conversation_id, resolved_conversation);
          ELSIF NEW.tenant_id IS NULL THEN
            NEW.tenant_id := '00000000-0000-0000-0000-000000000001'::uuid;
          END IF;
          RETURN NEW;
        END $$;


--
-- Name: shb_touch_conversation(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.shb_touch_conversation() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
          NEW.updated_at := now();
          NEW.row_version := OLD.row_version + 1;
          RETURN NEW;
        END $$;


--
-- Name: shb_validate_conversation_group_tenant(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.shb_validate_conversation_group_tenant() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
          IF NEW.group_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM conversation_groups g
            WHERE g.id=NEW.group_id AND g.tenant_id=NEW.tenant_id
          ) THEN
            RAISE EXCEPTION 'conversation group must belong to the same tenant'
              USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: agent_config_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent_config_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    prompt_key text NOT NULL,
    environment text NOT NULL,
    version integer NOT NULL,
    action text NOT NULL,
    actor text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_agent_config_events_action CHECK ((action = ANY (ARRAY['version_created'::text, 'activated'::text])))
);


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: applications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.applications (
    id text NOT NULL,
    owner_id text,
    product_id text,
    loan_amount_vnd bigint,
    loan_type text,
    collateral_id text,
    status text,
    credit_ok integer,
    legal_ok integer,
    human_approval text,
    approval_ref text,
    created_at text,
    party_id text
);


--
-- Name: approval_execution_attempts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.approval_execution_attempts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    approval_id uuid,
    attempt_no integer NOT NULL,
    worker_id text NOT NULL,
    status text NOT NULL,
    error_code text,
    result_snapshot jsonb,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    ended_at timestamp with time zone,
    tenant_id uuid DEFAULT '00000000-0000-0000-0000-000000000001'::uuid NOT NULL,
    CONSTRAINT ck_approval_attempts_number CHECK ((attempt_no > 0)),
    CONSTRAINT ck_approval_attempts_status CHECK ((status = ANY (ARRAY['running'::text, 'succeeded'::text, 'failed'::text, 'timeout'::text, 'cancelled'::text])))
);


--
-- Name: approvals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.approvals (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    conv_id text NOT NULL,
    task_id uuid,
    action text NOT NULL,
    payload jsonb NOT NULL,
    payload_hash text NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    decided_by text,
    decided_at timestamp with time zone,
    reason text,
    used_at timestamp with time zone,
    receipt jsonb,
    exec_attempts integer DEFAULT 0 NOT NULL,
    system_assessment_id integer,
    system_lane text,
    system_recommendation text,
    conversation_id uuid,
    idempotency_key text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    row_version integer DEFAULT 0 NOT NULL,
    tenant_id uuid DEFAULT '00000000-0000-0000-0000-000000000001'::uuid NOT NULL,
    CONSTRAINT ck_approvals_status CHECK ((status = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text, 'used'::text, 'exec_failed'::text]))),
    CONSTRAINT ck_approvals_system_lane CHECK (((system_lane IS NULL) OR (system_lane = ANY (ARRAY['green'::text, 'yellow'::text, 'red'::text])))),
    CONSTRAINT ck_approvals_system_recommendation CHECK (((system_recommendation IS NULL) OR (system_recommendation = ANY (ARRAY['auto-eligible'::text, 'human-review'::text, 'reject-recommended'::text])))),
    CONSTRAINT ck_approvals_used_receipt CHECK (((status = 'used'::text) = ((receipt IS NOT NULL) AND (used_at IS NOT NULL))))
);


--
-- Name: assessments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assessments (
    id integer NOT NULL,
    owner_id text,
    loan_type text,
    loan_amount_vnd bigint,
    lane text,
    criteria_json text,
    basis text,
    created_at text,
    party_id text,
    tenant_id uuid DEFAULT COALESCE((NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid, '00000000-0000-0000-0000-000000000001'::uuid) NOT NULL
);


--
-- Name: assessments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.assessments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assessments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.assessments_id_seq OWNED BY public.assessments.id;


--
-- Name: assumptions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assumptions (
    key character varying NOT NULL,
    value text
);


--
-- Name: businesses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.businesses (
    id character varying NOT NULL,
    name text,
    sector text,
    annual_revenue bigint,
    equity bigint,
    years_operating integer,
    tax_code text,
    address text
);


--
-- Name: cards; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cards (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    conv_id text NOT NULL,
    task_id uuid,
    type text NOT NULL,
    data jsonb NOT NULL,
    ts timestamp with time zone NOT NULL,
    conversation_id uuid,
    tenant_id uuid DEFAULT '00000000-0000-0000-0000-000000000001'::uuid NOT NULL
);


--
-- Name: cic_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cic_records (
    owner_id character varying NOT NULL,
    cic_group integer,
    history_note text,
    party_id text
);


--
-- Name: collateral_legal; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.collateral_legal (
    collateral_id character varying NOT NULL,
    dispute_status text,
    zoning_status text,
    note text
);


--
-- Name: collaterals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.collaterals (
    id character varying NOT NULL,
    owner_id character varying,
    type text,
    appraised_value bigint,
    docs_status text,
    party_id text
);


--
-- Name: consent_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.consent_records (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    subject_type text NOT NULL,
    subject_ref text NOT NULL,
    purpose text NOT NULL,
    wording_version text NOT NULL,
    wording_checksum character varying(64) NOT NULL,
    granted boolean NOT NULL,
    recorded_at timestamp with time zone DEFAULT now() NOT NULL,
    granted_at timestamp with time zone,
    actor text NOT NULL,
    source text NOT NULL,
    source_ref text NOT NULL,
    CONSTRAINT ck_consent_actor CHECK ((btrim(actor) <> ''::text)),
    CONSTRAINT ck_consent_granted_at CHECK ((((granted IS TRUE) AND (granted_at IS NOT NULL)) OR ((granted IS FALSE) AND (granted_at IS NULL)))),
    CONSTRAINT ck_consent_purpose CHECK ((purpose = 'pre_pilot_shadow_preassessment'::text)),
    CONSTRAINT ck_consent_source CHECK ((source = 'customer_form'::text)),
    CONSTRAINT ck_consent_source_ref CHECK ((btrim(source_ref) <> ''::text)),
    CONSTRAINT ck_consent_subject_ref CHECK ((btrim(subject_ref) <> ''::text)),
    CONSTRAINT ck_consent_subject_type CHECK ((subject_type = ANY (ARRAY['user'::text, 'external_party'::text]))),
    CONSTRAINT ck_consent_wording_checksum CHECK (((wording_checksum)::text ~ '^[0-9a-f]{64}$'::text)),
    CONSTRAINT ck_consent_wording_version CHECK ((wording_version ~ '^v[1-9][0-9]*$'::text))
);


--
-- Name: conversation_groups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conversation_groups (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    name text NOT NULL,
    created_by text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_conversation_groups_name CHECK (((char_length(btrim(name)) >= 1) AND (char_length(btrim(name)) <= 80)))
);


--
-- Name: conversations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conversations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id text,
    title text,
    status text,
    sdk_session_id text,
    created_at timestamp with time zone NOT NULL,
    provider text,
    model text,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    row_version integer DEFAULT 0 NOT NULL,
    tenant_id uuid DEFAULT '00000000-0000-0000-0000-000000000001'::uuid NOT NULL,
    group_id uuid
);


--
-- Name: customers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.customers (
    id character varying NOT NULL,
    full_name text,
    age integer,
    occupation text,
    monthly_income bigint,
    region text,
    id_number text,
    address text,
    segment text
);


--
-- Name: disbursements; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.disbursements (
    id text NOT NULL,
    application_id text,
    amount_vnd bigint,
    beneficiary text,
    status text,
    executed_at text,
    receipt_code text
);


--
-- Name: employment_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.employment_records (
    owner_id text NOT NULL,
    employer text,
    "position" text,
    tenure_months integer,
    verified_income_vnd bigint,
    status text,
    verified_at text,
    party_id text
);


--
-- Name: external_case_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.external_case_links (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source_system text NOT NULL,
    external_case_id text NOT NULL,
    internal_application_id text,
    party_reference text,
    assigned_rm_subject text,
    product_code text,
    loan_amount_vnd bigint,
    document_refs jsonb DEFAULT '[]'::jsonb NOT NULL,
    missing_fields jsonb DEFAULT '[]'::jsonb NOT NULL,
    source_version bigint NOT NULL,
    content_hash character varying(64) NOT NULL,
    case_status text NOT NULL,
    data_as_of timestamp with time zone NOT NULL,
    conversation_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    synced_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid DEFAULT '00000000-0000-0000-0000-000000000001'::uuid NOT NULL,
    CONSTRAINT ck_external_case_amount CHECK (((loan_amount_vnd IS NULL) OR (loan_amount_vnd >= 0))),
    CONSTRAINT ck_external_case_document_refs CHECK ((jsonb_typeof(document_refs) = 'array'::text)),
    CONSTRAINT ck_external_case_missing_fields CHECK ((jsonb_typeof(missing_fields) = 'array'::text)),
    CONSTRAINT ck_external_case_source_version CHECK ((source_version > 0)),
    CONSTRAINT ck_external_case_status CHECK ((case_status = ANY (ARRAY['received'::text, 'missing_information'::text, 'ready_for_preassessment'::text, 'preassessment_in_progress'::text, 'needs_specialist'::text, 'ready_for_handover'::text, 'cancelled'::text])))
);


--
-- Name: integration_inbox; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.integration_inbox (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source_system text NOT NULL,
    event_id text NOT NULL,
    event_type text NOT NULL,
    schema_version integer NOT NULL,
    external_case_id text NOT NULL,
    source_version bigint NOT NULL,
    payload jsonb NOT NULL,
    payload_hash character varying(64) NOT NULL,
    receipt jsonb NOT NULL,
    received_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_id uuid DEFAULT '00000000-0000-0000-0000-000000000001'::uuid NOT NULL,
    CONSTRAINT ck_integration_inbox_payload CHECK ((jsonb_typeof(payload) = 'object'::text)),
    CONSTRAINT ck_integration_inbox_receipt CHECK ((jsonb_typeof(receipt) = 'object'::text)),
    CONSTRAINT ck_integration_inbox_schema_version CHECK ((schema_version > 0)),
    CONSTRAINT ck_integration_inbox_source_version CHECK ((source_version > 0))
);


--
-- Name: interaction_notes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.interaction_notes (
    note_id integer NOT NULL,
    owner_id text NOT NULL,
    ts text NOT NULL,
    channel text NOT NULL,
    rm text NOT NULL,
    note_text text NOT NULL,
    embedding bytea,
    party_id text
);


--
-- Name: legal_requirements; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.legal_requirements (
    loan_type text NOT NULL,
    doc_code text NOT NULL,
    doc_name text,
    mandatory integer
);


--
-- Name: loans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.loans (
    loan_id character varying NOT NULL,
    owner_id character varying,
    principal bigint,
    outstanding bigint,
    monthly_payment bigint,
    status text,
    party_id text
);


--
-- Name: messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.messages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    conv_id text NOT NULL,
    ts timestamp with time zone NOT NULL,
    sender text,
    content text,
    meta jsonb,
    conversation_id uuid,
    tenant_id uuid DEFAULT '00000000-0000-0000-0000-000000000001'::uuid NOT NULL
);


--
-- Name: owner_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.owner_documents (
    owner_id character varying NOT NULL,
    doc_code text NOT NULL,
    status text,
    party_id text
);


--
-- Name: police_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.police_records (
    owner_id text NOT NULL,
    id_number text,
    full_name text,
    address text,
    criminal_status text,
    record_type text,
    record_year integer,
    notes text,
    party_id text
);


--
-- Name: shadow_reviews; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.shadow_reviews (
    approval_id uuid NOT NULL,
    conv_id text NOT NULL,
    system_lane text,
    system_recommendation text NOT NULL,
    human_decision text NOT NULL,
    human_reason text,
    decided_at timestamp with time zone NOT NULL,
    match boolean,
    conversation_id uuid,
    tenant_id uuid DEFAULT '00000000-0000-0000-0000-000000000001'::uuid NOT NULL,
    CONSTRAINT ck_shadow_reviews_human_decision CHECK ((human_decision = ANY (ARRAY['approved'::text, 'rejected'::text]))),
    CONSTRAINT ck_shadow_reviews_system_lane CHECK (((system_lane IS NULL) OR (system_lane = ANY (ARRAY['green'::text, 'yellow'::text, 'red'::text])))),
    CONSTRAINT ck_shadow_reviews_system_recommendation CHECK ((system_recommendation = ANY (ARRAY['auto-eligible'::text, 'human-review'::text, 'reject-recommended'::text])))
);


--
-- Name: tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tasks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    conv_id text NOT NULL,
    role text,
    title text,
    status text,
    input jsonb,
    result jsonb,
    queued_at timestamp with time zone,
    started_at timestamp with time zone,
    ended_at timestamp with time zone,
    cost jsonb,
    input_tokens bigint,
    output_tokens bigint,
    cache_read_tokens bigint,
    cache_create_tokens bigint,
    duration_ms bigint,
    model text,
    conversation_id uuid,
    parent_task_id uuid,
    attempt_count integer DEFAULT 0 NOT NULL,
    lease_owner text,
    lease_until timestamp with time zone,
    heartbeat_at timestamp with time zone,
    row_version integer DEFAULT 0 NOT NULL,
    tenant_id uuid DEFAULT '00000000-0000-0000-0000-000000000001'::uuid NOT NULL,
    CONSTRAINT ck_tasks_attempt_count CHECK ((attempt_count >= 0)),
    CONSTRAINT ck_tasks_lease_pair CHECK (((lease_owner IS NULL) = (lease_until IS NULL)))
);


--
-- Name: tool_calls; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tool_calls (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    task_id uuid,
    conv_id text,
    ts timestamp with time zone DEFAULT now() NOT NULL,
    actor text NOT NULL,
    tool text NOT NULL,
    input jsonb,
    output jsonb,
    cost jsonb,
    conversation_id uuid,
    tenant_id uuid DEFAULT '00000000-0000-0000-0000-000000000001'::uuid NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    username character varying NOT NULL,
    pass_hash text,
    role text NOT NULL,
    owner_id text,
    email text,
    google_sub text,
    party_id text,
    tenant_id uuid DEFAULT '00000000-0000-0000-0000-000000000001'::uuid NOT NULL
);


--
-- Name: operational_data_issues; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.operational_data_issues AS
 SELECT 'missing_conversation'::text AS issue_type,
    'messages'::text AS entity_table,
    (messages.id)::text AS entity_key,
    messages.conv_id AS reference_value
   FROM public.messages
  WHERE ((messages.conv_id IS NOT NULL) AND (messages.conversation_id IS NULL))
UNION ALL
 SELECT 'missing_conversation'::text AS issue_type,
    'tasks'::text AS entity_table,
    (tasks.id)::text AS entity_key,
    tasks.conv_id AS reference_value
   FROM public.tasks
  WHERE ((tasks.conv_id IS NOT NULL) AND (tasks.conversation_id IS NULL))
UNION ALL
 SELECT 'missing_conversation'::text AS issue_type,
    'cards'::text AS entity_table,
    (cards.id)::text AS entity_key,
    cards.conv_id AS reference_value
   FROM public.cards
  WHERE ((cards.conv_id IS NOT NULL) AND (cards.conversation_id IS NULL))
UNION ALL
 SELECT 'missing_conversation'::text AS issue_type,
    'tool_calls'::text AS entity_table,
    (tool_calls.id)::text AS entity_key,
    tool_calls.conv_id AS reference_value
   FROM public.tool_calls
  WHERE ((tool_calls.conv_id IS NOT NULL) AND (tool_calls.conversation_id IS NULL))
UNION ALL
 SELECT 'missing_conversation'::text AS issue_type,
    'approvals'::text AS entity_table,
    (approvals.id)::text AS entity_key,
    approvals.conv_id AS reference_value
   FROM public.approvals
  WHERE ((approvals.conv_id IS NOT NULL) AND (approvals.conversation_id IS NULL))
UNION ALL
 SELECT 'missing_conversation'::text AS issue_type,
    'shadow_reviews'::text AS entity_table,
    (shadow_reviews.approval_id)::text AS entity_key,
    shadow_reviews.conv_id AS reference_value
   FROM public.shadow_reviews
  WHERE ((shadow_reviews.conv_id IS NOT NULL) AND (shadow_reviews.conversation_id IS NULL))
UNION ALL
 SELECT 'missing_party'::text AS issue_type,
    'users'::text AS entity_table,
    (users.ctid)::text AS entity_key,
    users.owner_id AS reference_value
   FROM public.users
  WHERE ((users.owner_id IS NOT NULL) AND (users.party_id IS NULL))
UNION ALL
 SELECT 'missing_party'::text AS issue_type,
    'loans'::text AS entity_table,
    (loans.ctid)::text AS entity_key,
    (loans.owner_id)::text AS reference_value
   FROM public.loans
  WHERE ((loans.owner_id IS NOT NULL) AND (loans.party_id IS NULL))
UNION ALL
 SELECT 'missing_party'::text AS issue_type,
    'cic_records'::text AS entity_table,
    (cic_records.ctid)::text AS entity_key,
    (cic_records.owner_id)::text AS reference_value
   FROM public.cic_records
  WHERE ((cic_records.owner_id IS NOT NULL) AND (cic_records.party_id IS NULL))
UNION ALL
 SELECT 'missing_party'::text AS issue_type,
    'collaterals'::text AS entity_table,
    (collaterals.ctid)::text AS entity_key,
    (collaterals.owner_id)::text AS reference_value
   FROM public.collaterals
  WHERE ((collaterals.owner_id IS NOT NULL) AND (collaterals.party_id IS NULL))
UNION ALL
 SELECT 'missing_party'::text AS issue_type,
    'owner_documents'::text AS entity_table,
    (owner_documents.ctid)::text AS entity_key,
    (owner_documents.owner_id)::text AS reference_value
   FROM public.owner_documents
  WHERE ((owner_documents.owner_id IS NOT NULL) AND (owner_documents.party_id IS NULL))
UNION ALL
 SELECT 'missing_party'::text AS issue_type,
    'police_records'::text AS entity_table,
    (police_records.ctid)::text AS entity_key,
    police_records.owner_id AS reference_value
   FROM public.police_records
  WHERE ((police_records.owner_id IS NOT NULL) AND (police_records.party_id IS NULL))
UNION ALL
 SELECT 'missing_party'::text AS issue_type,
    'employment_records'::text AS entity_table,
    (employment_records.ctid)::text AS entity_key,
    employment_records.owner_id AS reference_value
   FROM public.employment_records
  WHERE ((employment_records.owner_id IS NOT NULL) AND (employment_records.party_id IS NULL))
UNION ALL
 SELECT 'missing_party'::text AS issue_type,
    'assessments'::text AS entity_table,
    (assessments.ctid)::text AS entity_key,
    assessments.owner_id AS reference_value
   FROM public.assessments
  WHERE ((assessments.owner_id IS NOT NULL) AND (assessments.party_id IS NULL))
UNION ALL
 SELECT 'missing_party'::text AS issue_type,
    'applications'::text AS entity_table,
    (applications.ctid)::text AS entity_key,
    applications.owner_id AS reference_value
   FROM public.applications
  WHERE ((applications.owner_id IS NOT NULL) AND (applications.party_id IS NULL))
UNION ALL
 SELECT 'missing_party'::text AS issue_type,
    'interaction_notes'::text AS entity_table,
    (interaction_notes.ctid)::text AS entity_key,
    interaction_notes.owner_id AS reference_value
   FROM public.interaction_notes
  WHERE ((interaction_notes.owner_id IS NOT NULL) AND (interaction_notes.party_id IS NULL))
UNION ALL
 SELECT 'missing_approval'::text AS issue_type,
    'shadow_reviews'::text AS entity_table,
    (s.approval_id)::text AS entity_key,
    (s.approval_id)::text AS reference_value
   FROM public.shadow_reviews s
  WHERE (NOT (EXISTS ( SELECT 1
           FROM public.approvals a
          WHERE (a.id = s.approval_id))));


--
-- Name: outbox_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.outbox_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    aggregate_type text NOT NULL,
    aggregate_id text NOT NULL,
    event_type text NOT NULL,
    payload jsonb NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    attempt_count integer DEFAULT 0 NOT NULL,
    available_at timestamp with time zone DEFAULT now() NOT NULL,
    locked_by text,
    locked_until timestamp with time zone,
    published_at timestamp with time zone,
    last_error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_outbox_attempt_count CHECK ((attempt_count >= 0)),
    CONSTRAINT ck_outbox_lock_pair CHECK (((locked_by IS NULL) = (locked_until IS NULL))),
    CONSTRAINT ck_outbox_status CHECK ((status = ANY (ARRAY['pending'::text, 'publishing'::text, 'published'::text, 'dead'::text])))
);


--
-- Name: parties; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.parties (
    owner_id text NOT NULL,
    party_type text NOT NULL,
    display_name text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_parties_type CHECK ((party_type = ANY (ARRAY['customer'::text, 'business'::text])))
);


--
-- Name: party_relations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.party_relations (
    from_id text NOT NULL,
    to_id text NOT NULL,
    relation text NOT NULL,
    pct double precision,
    from_party_id text,
    to_party_id text
);


--
-- Name: procedure_steps; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.procedure_steps (
    application_id text NOT NULL,
    step text NOT NULL,
    status text,
    done_at text
);


--
-- Name: products; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.products (
    id text NOT NULL,
    name text,
    loan_type text,
    rate_annual double precision,
    term_max_months integer,
    amount_min_vnd bigint,
    amount_max_vnd bigint,
    fee_pct double precision,
    income_min_vnd bigint,
    cic_max_group integer,
    segment text,
    status text,
    note text
);


--
-- Name: prompt_bindings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.prompt_bindings (
    prompt_key text NOT NULL,
    environment text DEFAULT 'default'::text NOT NULL,
    version_id uuid NOT NULL,
    activated_by text DEFAULT 'bootstrap'::text NOT NULL,
    activated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_prompt_bindings_environment CHECK ((length(environment) > 0))
);


--
-- Name: prompt_definitions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.prompt_definitions (
    prompt_key text NOT NULL,
    scope text NOT NULL,
    description text,
    variables jsonb DEFAULT '[]'::jsonb NOT NULL,
    default_file text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_prompt_definitions_variables CHECK ((jsonb_typeof(variables) = 'array'::text))
);


--
-- Name: prompt_versions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.prompt_versions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    prompt_key text NOT NULL,
    version integer NOT NULL,
    content text NOT NULL,
    checksum character varying(64) NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_by text DEFAULT 'bootstrap'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_prompt_versions_content CHECK ((length(content) > 0)),
    CONSTRAINT ck_prompt_versions_number CHECK ((version > 0))
);


--
-- Name: restricted_purposes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.restricted_purposes (
    purpose_code text NOT NULL,
    purpose_name text,
    restriction text,
    legal_basis text
);


--
-- Name: task_attempts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.task_attempts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    task_id uuid,
    conversation_id uuid,
    attempt_no integer NOT NULL,
    worker_id text NOT NULL,
    status text NOT NULL,
    error_code text,
    metrics jsonb,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    ended_at timestamp with time zone,
    tenant_id uuid DEFAULT '00000000-0000-0000-0000-000000000001'::uuid NOT NULL,
    CONSTRAINT ck_task_attempts_number CHECK ((attempt_no > 0)),
    CONSTRAINT ck_task_attempts_status CHECK ((status = ANY (ARRAY['running'::text, 'succeeded'::text, 'failed'::text, 'timeout'::text, 'cancelled'::text])))
);


--
-- Name: tenants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenants (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    slug text NOT NULL,
    name text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_tenants_name_not_blank CHECK ((btrim(name) <> ''::text)),
    CONSTRAINT ck_tenants_slug_not_blank CHECK ((btrim(slug) <> ''::text))
);


--
-- Name: wiki_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wiki_links (
    from_page text NOT NULL,
    to_page text NOT NULL
);


--
-- Name: wiki_pages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wiki_pages (
    id text NOT NULL,
    role text NOT NULL,
    title text NOT NULL,
    topic text,
    tags text,
    legal_basis text,
    effective_from text,
    effective_to text,
    status text DEFAULT 'active'::text,
    body text NOT NULL,
    source_file text,
    so_hieu text,
    dieu text,
    amended_by text,
    source_url text,
    crawled_at text
);


--
-- Name: assessments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessments ALTER COLUMN id SET DEFAULT nextval('public.assessments_id_seq'::regclass);


--
-- Name: agent_config_events agent_config_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_config_events
    ADD CONSTRAINT agent_config_events_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: applications applications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT applications_pkey PRIMARY KEY (id);


--
-- Name: approval_execution_attempts approval_execution_attempts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.approval_execution_attempts
    ADD CONSTRAINT approval_execution_attempts_pkey PRIMARY KEY (id);


--
-- Name: approvals approvals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.approvals
    ADD CONSTRAINT approvals_pkey PRIMARY KEY (id);


--
-- Name: assessments assessments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessments
    ADD CONSTRAINT assessments_pkey PRIMARY KEY (id);


--
-- Name: assumptions assumptions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assumptions
    ADD CONSTRAINT assumptions_pkey PRIMARY KEY (key);


--
-- Name: businesses businesses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.businesses
    ADD CONSTRAINT businesses_pkey PRIMARY KEY (id);


--
-- Name: cards cards_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cards
    ADD CONSTRAINT cards_pkey PRIMARY KEY (id);


--
-- Name: cic_records cic_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cic_records
    ADD CONSTRAINT cic_records_pkey PRIMARY KEY (owner_id);


--
-- Name: collateral_legal collateral_legal_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.collateral_legal
    ADD CONSTRAINT collateral_legal_pkey PRIMARY KEY (collateral_id);


--
-- Name: collaterals collaterals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.collaterals
    ADD CONSTRAINT collaterals_pkey PRIMARY KEY (id);


--
-- Name: consent_records consent_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consent_records
    ADD CONSTRAINT consent_records_pkey PRIMARY KEY (id);


--
-- Name: conversation_groups conversation_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_groups
    ADD CONSTRAINT conversation_groups_pkey PRIMARY KEY (id);


--
-- Name: conversations conversations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_pkey PRIMARY KEY (id);


--
-- Name: customers customers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_pkey PRIMARY KEY (id);


--
-- Name: disbursements disbursements_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disbursements
    ADD CONSTRAINT disbursements_pkey PRIMARY KEY (id);


--
-- Name: employment_records employment_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employment_records
    ADD CONSTRAINT employment_records_pkey PRIMARY KEY (owner_id);


--
-- Name: external_case_links external_case_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.external_case_links
    ADD CONSTRAINT external_case_links_pkey PRIMARY KEY (id);


--
-- Name: integration_inbox integration_inbox_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.integration_inbox
    ADD CONSTRAINT integration_inbox_pkey PRIMARY KEY (id);


--
-- Name: interaction_notes interaction_notes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interaction_notes
    ADD CONSTRAINT interaction_notes_pkey PRIMARY KEY (note_id);


--
-- Name: legal_requirements legal_requirements_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_requirements
    ADD CONSTRAINT legal_requirements_pkey PRIMARY KEY (loan_type, doc_code);


--
-- Name: loans loans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.loans
    ADD CONSTRAINT loans_pkey PRIMARY KEY (loan_id);


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id);


--
-- Name: outbox_events outbox_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outbox_events
    ADD CONSTRAINT outbox_events_pkey PRIMARY KEY (id);


--
-- Name: owner_documents owner_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.owner_documents
    ADD CONSTRAINT owner_documents_pkey PRIMARY KEY (owner_id, doc_code);


--
-- Name: parties parties_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parties
    ADD CONSTRAINT parties_pkey PRIMARY KEY (owner_id);


--
-- Name: party_relations party_relations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.party_relations
    ADD CONSTRAINT party_relations_pkey PRIMARY KEY (from_id, to_id, relation);


--
-- Name: police_records police_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.police_records
    ADD CONSTRAINT police_records_pkey PRIMARY KEY (owner_id);


--
-- Name: procedure_steps procedure_steps_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.procedure_steps
    ADD CONSTRAINT procedure_steps_pkey PRIMARY KEY (application_id, step);


--
-- Name: products products_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_pkey PRIMARY KEY (id);


--
-- Name: prompt_bindings prompt_bindings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_bindings
    ADD CONSTRAINT prompt_bindings_pkey PRIMARY KEY (prompt_key, environment);


--
-- Name: prompt_definitions prompt_definitions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_definitions
    ADD CONSTRAINT prompt_definitions_pkey PRIMARY KEY (prompt_key);


--
-- Name: prompt_versions prompt_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_versions
    ADD CONSTRAINT prompt_versions_pkey PRIMARY KEY (id);


--
-- Name: restricted_purposes restricted_purposes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.restricted_purposes
    ADD CONSTRAINT restricted_purposes_pkey PRIMARY KEY (purpose_code);


--
-- Name: shadow_reviews shadow_reviews_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shadow_reviews
    ADD CONSTRAINT shadow_reviews_pkey PRIMARY KEY (approval_id);


--
-- Name: task_attempts task_attempts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_attempts
    ADD CONSTRAINT task_attempts_pkey PRIMARY KEY (id);


--
-- Name: tasks tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (id);


--
-- Name: tenants tenants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);


--
-- Name: tool_calls tool_calls_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tool_calls
    ADD CONSTRAINT tool_calls_pkey PRIMARY KEY (id);


--
-- Name: approval_execution_attempts uq_approval_attempts_number; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.approval_execution_attempts
    ADD CONSTRAINT uq_approval_attempts_number UNIQUE (approval_id, attempt_no);


--
-- Name: approvals uq_approvals_idempotency_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.approvals
    ADD CONSTRAINT uq_approvals_idempotency_key UNIQUE (idempotency_key);


--
-- Name: consent_records uq_consent_records_source_purpose; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consent_records
    ADD CONSTRAINT uq_consent_records_source_purpose UNIQUE (tenant_id, source, source_ref, purpose);


--
-- Name: external_case_links uq_external_case_conversation; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.external_case_links
    ADD CONSTRAINT uq_external_case_conversation UNIQUE (conversation_id);


--
-- Name: external_case_links uq_external_case_source_identity; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.external_case_links
    ADD CONSTRAINT uq_external_case_source_identity UNIQUE (source_system, external_case_id);


--
-- Name: integration_inbox uq_integration_inbox_source_event; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.integration_inbox
    ADD CONSTRAINT uq_integration_inbox_source_event UNIQUE (source_system, event_id);


--
-- Name: prompt_versions uq_prompt_versions_checksum; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_versions
    ADD CONSTRAINT uq_prompt_versions_checksum UNIQUE (prompt_key, checksum);


--
-- Name: prompt_versions uq_prompt_versions_key_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_versions
    ADD CONSTRAINT uq_prompt_versions_key_id UNIQUE (prompt_key, id);


--
-- Name: prompt_versions uq_prompt_versions_number; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_versions
    ADD CONSTRAINT uq_prompt_versions_number UNIQUE (prompt_key, version);


--
-- Name: task_attempts uq_task_attempts_number; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_attempts
    ADD CONSTRAINT uq_task_attempts_number UNIQUE (task_id, attempt_no);


--
-- Name: tenants uq_tenants_slug; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT uq_tenants_slug UNIQUE (slug);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: wiki_links wiki_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_links
    ADD CONSTRAINT wiki_links_pkey PRIMARY KEY (from_page, to_page);


--
-- Name: wiki_pages wiki_pages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_pages
    ADD CONSTRAINT wiki_pages_pkey PRIMARY KEY (id);


--
-- Name: ix_agent_config_events_prompt_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_agent_config_events_prompt_created ON public.agent_config_events USING btree (prompt_key, created_at);


--
-- Name: ix_applications_owner_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_applications_owner_id ON public.applications USING btree (owner_id);


--
-- Name: ix_applications_party_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_applications_party_id ON public.applications USING btree (party_id);


--
-- Name: ix_approvals_conv_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_approvals_conv_id ON public.approvals USING btree (conv_id);


--
-- Name: ix_approvals_conversation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_approvals_conversation_id ON public.approvals USING btree (conversation_id);


--
-- Name: ix_approvals_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_approvals_key ON public.approvals USING btree (conv_id, action, payload_hash);


--
-- Name: ix_approvals_pending_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_approvals_pending_created ON public.approvals USING btree (created_at) WHERE (status = 'pending'::text);


--
-- Name: ix_approvals_tenant_status_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_approvals_tenant_status_created ON public.approvals USING btree (tenant_id, status, created_at);


--
-- Name: ix_assessments_party_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessments_party_id ON public.assessments USING btree (party_id);


--
-- Name: ix_assessments_tenant_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessments_tenant_created ON public.assessments USING btree (tenant_id, created_at);


--
-- Name: ix_cards_conversation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cards_conversation_id ON public.cards USING btree (conversation_id);


--
-- Name: ix_cards_tenant_conv_ts; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cards_tenant_conv_ts ON public.cards USING btree (tenant_id, conv_id, ts);


--
-- Name: ix_cic_records_party_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cic_records_party_id ON public.cic_records USING btree (party_id);


--
-- Name: ix_collaterals_party_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_collaterals_party_id ON public.collaterals USING btree (party_id);


--
-- Name: ix_consent_records_tenant_recorded; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_consent_records_tenant_recorded ON public.consent_records USING btree (tenant_id, recorded_at);


--
-- Name: ix_conversation_groups_tenant_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conversation_groups_tenant_created ON public.conversation_groups USING btree (tenant_id, created_at);


--
-- Name: ix_conversations_tenant_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conversations_tenant_created ON public.conversations USING btree (tenant_id, created_at);


--
-- Name: ix_conversations_tenant_group_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conversations_tenant_group_created ON public.conversations USING btree (tenant_id, group_id, created_at);


--
-- Name: ix_disbursements_application_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_disbursements_application_id ON public.disbursements USING btree (application_id);


--
-- Name: ix_employment_records_party_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_employment_records_party_id ON public.employment_records USING btree (party_id);


--
-- Name: ix_external_case_links_tenant_status_synced; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_external_case_links_tenant_status_synced ON public.external_case_links USING btree (tenant_id, case_status, synced_at);


--
-- Name: ix_external_case_source_synced; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_external_case_source_synced ON public.external_case_links USING btree (source_system, synced_at);


--
-- Name: ix_external_case_status_synced; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_external_case_status_synced ON public.external_case_links USING btree (case_status, synced_at);


--
-- Name: ix_integration_inbox_case_received; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_integration_inbox_case_received ON public.integration_inbox USING btree (source_system, external_case_id, received_at);


--
-- Name: ix_integration_inbox_tenant_case_received; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_integration_inbox_tenant_case_received ON public.integration_inbox USING btree (tenant_id, source_system, external_case_id, received_at);


--
-- Name: ix_interaction_notes_owner_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_interaction_notes_owner_id ON public.interaction_notes USING btree (owner_id);


--
-- Name: ix_interaction_notes_party_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_interaction_notes_party_id ON public.interaction_notes USING btree (party_id);


--
-- Name: ix_loans_party_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_loans_party_id ON public.loans USING btree (party_id);


--
-- Name: ix_messages_conversation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_messages_conversation_id ON public.messages USING btree (conversation_id);


--
-- Name: ix_messages_tenant_ts; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_messages_tenant_ts ON public.messages USING btree (tenant_id, ts);


--
-- Name: ix_outbox_aggregate; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_outbox_aggregate ON public.outbox_events USING btree (aggregate_type, aggregate_id, created_at);


--
-- Name: ix_outbox_claim; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_outbox_claim ON public.outbox_events USING btree (available_at, created_at) WHERE (status = 'pending'::text);


--
-- Name: ix_owner_documents_party_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_owner_documents_party_id ON public.owner_documents USING btree (party_id);


--
-- Name: ix_party_relations_from_party_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_party_relations_from_party_id ON public.party_relations USING btree (from_party_id);


--
-- Name: ix_party_relations_to_party_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_party_relations_to_party_id ON public.party_relations USING btree (to_party_id);


--
-- Name: ix_police_records_party_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_police_records_party_id ON public.police_records USING btree (party_id);


--
-- Name: ix_prompt_versions_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_prompt_versions_created ON public.prompt_versions USING btree (prompt_key, created_at);


--
-- Name: ix_shadow_reviews_conversation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_shadow_reviews_conversation_id ON public.shadow_reviews USING btree (conversation_id);


--
-- Name: ix_shadow_reviews_decided_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_shadow_reviews_decided_at ON public.shadow_reviews USING btree (decided_at);


--
-- Name: ix_shadow_reviews_tenant_decided; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_shadow_reviews_tenant_decided ON public.shadow_reviews USING btree (tenant_id, decided_at);


--
-- Name: ix_task_attempts_conversation_started; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_task_attempts_conversation_started ON public.task_attempts USING btree (conversation_id, started_at);


--
-- Name: ix_tasks_claim; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tasks_claim ON public.tasks USING btree (queued_at) WHERE (status = 'queued'::text);


--
-- Name: ix_tasks_conversation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tasks_conversation_id ON public.tasks USING btree (conversation_id);


--
-- Name: ix_tasks_expired_lease; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tasks_expired_lease ON public.tasks USING btree (lease_until) WHERE (lease_until IS NOT NULL);


--
-- Name: ix_tasks_tenant_ended; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tasks_tenant_ended ON public.tasks USING btree (tenant_id, ended_at);


--
-- Name: ix_tool_calls_conv; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tool_calls_conv ON public.tool_calls USING btree (conv_id);


--
-- Name: ix_tool_calls_conversation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tool_calls_conversation_id ON public.tool_calls USING btree (conversation_id);


--
-- Name: ix_tool_calls_task_ts; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tool_calls_task_ts ON public.tool_calls USING btree (task_id, ts);


--
-- Name: ix_tool_calls_tenant_ts; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tool_calls_tenant_ts ON public.tool_calls USING btree (tenant_id, ts);


--
-- Name: ix_users_party_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_party_id ON public.users USING btree (party_id);


--
-- Name: ix_users_tenant_username; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_tenant_username ON public.users USING btree (tenant_id, username);


--
-- Name: uq_approval_attempts_one_success; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_approval_attempts_one_success ON public.approval_execution_attempts USING btree (approval_id) WHERE (status = 'succeeded'::text);


--
-- Name: uq_conversation_groups_tenant_name_ci; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_conversation_groups_tenant_name_ci ON public.conversation_groups USING btree (tenant_id, created_by, lower(name));


--
-- Name: uq_users_google_sub; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_users_google_sub ON public.users USING btree (google_sub);


--
-- Name: applications trg_applications_party_ref; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_applications_party_ref BEFORE INSERT OR UPDATE OF owner_id, party_id ON public.applications FOR EACH ROW EXECUTE FUNCTION public.shb_resolve_party_reference();


--
-- Name: approval_execution_attempts trg_approval_attempts_tenant; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_approval_attempts_tenant BEFORE INSERT OR UPDATE OF approval_id, tenant_id ON public.approval_execution_attempts FOR EACH ROW EXECUTE FUNCTION public.shb_sync_approval_attempt_tenant();


--
-- Name: approval_execution_attempts trg_approval_execution_attempts_tenant_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_approval_execution_attempts_tenant_immutable BEFORE UPDATE OF tenant_id ON public.approval_execution_attempts FOR EACH ROW EXECUTE FUNCTION public.shb_reject_tenant_change();


--
-- Name: approvals trg_approvals_conversation_ref; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_approvals_conversation_ref BEFORE INSERT OR UPDATE OF conv_id, conversation_id ON public.approvals FOR EACH ROW EXECUTE FUNCTION public.shb_resolve_conversation_reference();


--
-- Name: approvals trg_approvals_prepare; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_approvals_prepare BEFORE INSERT OR UPDATE ON public.approvals FOR EACH ROW EXECUTE FUNCTION public.shb_prepare_approval();


--
-- Name: approvals trg_approvals_tenant_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_approvals_tenant_immutable BEFORE UPDATE OF tenant_id ON public.approvals FOR EACH ROW EXECUTE FUNCTION public.shb_reject_tenant_change();


--
-- Name: assessments trg_assessments_party_ref; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_assessments_party_ref BEFORE INSERT OR UPDATE OF owner_id, party_id ON public.assessments FOR EACH ROW EXECUTE FUNCTION public.shb_resolve_party_reference();


--
-- Name: assessments trg_assessments_tenant_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_assessments_tenant_immutable BEFORE UPDATE OF tenant_id ON public.assessments FOR EACH ROW EXECUTE FUNCTION public.shb_reject_tenant_change();


--
-- Name: businesses trg_businesses_party; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_businesses_party BEFORE INSERT OR UPDATE OF id, name ON public.businesses FOR EACH ROW EXECUTE FUNCTION public.shb_sync_business_party();


--
-- Name: cards trg_cards_conversation_ref; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_cards_conversation_ref BEFORE INSERT OR UPDATE OF conv_id, conversation_id ON public.cards FOR EACH ROW EXECUTE FUNCTION public.shb_resolve_conversation_reference();


--
-- Name: cards trg_cards_tenant_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_cards_tenant_immutable BEFORE UPDATE OF tenant_id ON public.cards FOR EACH ROW EXECUTE FUNCTION public.shb_reject_tenant_change();


--
-- Name: cic_records trg_cic_records_party_ref; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_cic_records_party_ref BEFORE INSERT OR UPDATE OF owner_id, party_id ON public.cic_records FOR EACH ROW EXECUTE FUNCTION public.shb_resolve_party_reference();


--
-- Name: collaterals trg_collaterals_party_ref; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_collaterals_party_ref BEFORE INSERT OR UPDATE OF owner_id, party_id ON public.collaterals FOR EACH ROW EXECUTE FUNCTION public.shb_resolve_party_reference();


--
-- Name: consent_records trg_consent_records_append_only; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_consent_records_append_only BEFORE DELETE OR UPDATE ON public.consent_records FOR EACH ROW EXECUTE FUNCTION public.shb_reject_consent_mutation();


--
-- Name: consent_records trg_consent_records_tenant_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_consent_records_tenant_immutable BEFORE UPDATE OF tenant_id ON public.consent_records FOR EACH ROW EXECUTE FUNCTION public.shb_reject_tenant_change();


--
-- Name: conversation_groups trg_conversation_groups_tenant_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_conversation_groups_tenant_immutable BEFORE UPDATE OF tenant_id ON public.conversation_groups FOR EACH ROW EXECUTE FUNCTION public.shb_reject_tenant_change();


--
-- Name: conversations trg_conversations_group_tenant; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_conversations_group_tenant BEFORE INSERT OR UPDATE OF tenant_id, group_id ON public.conversations FOR EACH ROW EXECUTE FUNCTION public.shb_validate_conversation_group_tenant();


--
-- Name: conversations trg_conversations_tenant_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_conversations_tenant_immutable BEFORE UPDATE OF tenant_id ON public.conversations FOR EACH ROW EXECUTE FUNCTION public.shb_reject_tenant_change();


--
-- Name: conversations trg_conversations_touch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_conversations_touch BEFORE UPDATE ON public.conversations FOR EACH ROW EXECUTE FUNCTION public.shb_touch_conversation();


--
-- Name: customers trg_customers_party; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_customers_party BEFORE INSERT OR UPDATE OF id, full_name ON public.customers FOR EACH ROW EXECUTE FUNCTION public.shb_sync_customer_party();


--
-- Name: employment_records trg_employment_records_party_ref; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_employment_records_party_ref BEFORE INSERT OR UPDATE OF owner_id, party_id ON public.employment_records FOR EACH ROW EXECUTE FUNCTION public.shb_resolve_party_reference();


--
-- Name: external_case_links trg_external_case_links_tenant_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_external_case_links_tenant_immutable BEFORE UPDATE OF tenant_id ON public.external_case_links FOR EACH ROW EXECUTE FUNCTION public.shb_reject_tenant_change();


--
-- Name: integration_inbox trg_integration_inbox_tenant_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_integration_inbox_tenant_immutable BEFORE UPDATE OF tenant_id ON public.integration_inbox FOR EACH ROW EXECUTE FUNCTION public.shb_reject_tenant_change();


--
-- Name: interaction_notes trg_interaction_notes_party_ref; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_interaction_notes_party_ref BEFORE INSERT OR UPDATE OF owner_id, party_id ON public.interaction_notes FOR EACH ROW EXECUTE FUNCTION public.shb_resolve_party_reference();


--
-- Name: loans trg_loans_party_ref; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_loans_party_ref BEFORE INSERT OR UPDATE OF owner_id, party_id ON public.loans FOR EACH ROW EXECUTE FUNCTION public.shb_resolve_party_reference();


--
-- Name: messages trg_messages_conversation_ref; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_messages_conversation_ref BEFORE INSERT OR UPDATE OF conv_id, conversation_id ON public.messages FOR EACH ROW EXECUTE FUNCTION public.shb_resolve_conversation_reference();


--
-- Name: messages trg_messages_tenant_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_messages_tenant_immutable BEFORE UPDATE OF tenant_id ON public.messages FOR EACH ROW EXECUTE FUNCTION public.shb_reject_tenant_change();


--
-- Name: owner_documents trg_owner_documents_party_ref; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_owner_documents_party_ref BEFORE INSERT OR UPDATE OF owner_id, party_id ON public.owner_documents FOR EACH ROW EXECUTE FUNCTION public.shb_resolve_party_reference();


--
-- Name: party_relations trg_party_relations_refs; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_party_relations_refs BEFORE INSERT OR UPDATE ON public.party_relations FOR EACH ROW EXECUTE FUNCTION public.shb_resolve_relation_parties();


--
-- Name: police_records trg_police_records_party_ref; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_police_records_party_ref BEFORE INSERT OR UPDATE OF owner_id, party_id ON public.police_records FOR EACH ROW EXECUTE FUNCTION public.shb_resolve_party_reference();


--
-- Name: shadow_reviews trg_shadow_reviews_conversation_ref; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_shadow_reviews_conversation_ref BEFORE INSERT OR UPDATE OF conv_id, conversation_id ON public.shadow_reviews FOR EACH ROW EXECUTE FUNCTION public.shb_resolve_conversation_reference();


--
-- Name: shadow_reviews trg_shadow_reviews_tenant_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_shadow_reviews_tenant_immutable BEFORE UPDATE OF tenant_id ON public.shadow_reviews FOR EACH ROW EXECUTE FUNCTION public.shb_reject_tenant_change();


--
-- Name: task_attempts trg_task_attempts_tenant; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_task_attempts_tenant BEFORE INSERT OR UPDATE OF task_id, tenant_id ON public.task_attempts FOR EACH ROW EXECUTE FUNCTION public.shb_sync_task_attempt_tenant();


--
-- Name: task_attempts trg_task_attempts_tenant_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_task_attempts_tenant_immutable BEFORE UPDATE OF tenant_id ON public.task_attempts FOR EACH ROW EXECUTE FUNCTION public.shb_reject_tenant_change();


--
-- Name: tasks trg_tasks_conversation_ref; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_tasks_conversation_ref BEFORE INSERT OR UPDATE OF conv_id, conversation_id ON public.tasks FOR EACH ROW EXECUTE FUNCTION public.shb_resolve_conversation_reference();


--
-- Name: tasks trg_tasks_tenant_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_tasks_tenant_immutable BEFORE UPDATE OF tenant_id ON public.tasks FOR EACH ROW EXECUTE FUNCTION public.shb_reject_tenant_change();


--
-- Name: tool_calls trg_tool_calls_conversation_ref; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_tool_calls_conversation_ref BEFORE INSERT OR UPDATE OF conv_id, conversation_id ON public.tool_calls FOR EACH ROW EXECUTE FUNCTION public.shb_resolve_conversation_reference();


--
-- Name: tool_calls trg_tool_calls_tenant_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_tool_calls_tenant_immutable BEFORE UPDATE OF tenant_id ON public.tool_calls FOR EACH ROW EXECUTE FUNCTION public.shb_reject_tenant_change();


--
-- Name: users trg_users_party_ref; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_users_party_ref BEFORE INSERT OR UPDATE OF owner_id, party_id ON public.users FOR EACH ROW EXECUTE FUNCTION public.shb_resolve_party_reference();


--
-- Name: users trg_users_tenant_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_users_tenant_immutable BEFORE UPDATE OF tenant_id ON public.users FOR EACH ROW EXECUTE FUNCTION public.shb_reject_tenant_change();


--
-- Name: approval_execution_attempts approval_execution_attempts_approval_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.approval_execution_attempts
    ADD CONSTRAINT approval_execution_attempts_approval_id_fkey FOREIGN KEY (approval_id) REFERENCES public.approvals(id) ON DELETE SET NULL;


--
-- Name: consent_records consent_records_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consent_records
    ADD CONSTRAINT consent_records_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;


--
-- Name: conversation_groups conversation_groups_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_groups
    ADD CONSTRAINT conversation_groups_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;


--
-- Name: external_case_links external_case_links_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.external_case_links
    ADD CONSTRAINT external_case_links_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE SET NULL;


--
-- Name: applications fk_applications_party_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT fk_applications_party_id FOREIGN KEY (party_id) REFERENCES public.parties(owner_id) ON DELETE SET NULL;


--
-- Name: approval_execution_attempts fk_approval_execution_attempts_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.approval_execution_attempts
    ADD CONSTRAINT fk_approval_execution_attempts_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;


--
-- Name: approvals fk_approvals_conversation_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.approvals
    ADD CONSTRAINT fk_approvals_conversation_id FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE SET NULL;


--
-- Name: approvals fk_approvals_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.approvals
    ADD CONSTRAINT fk_approvals_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;


--
-- Name: assessments fk_assessments_party_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessments
    ADD CONSTRAINT fk_assessments_party_id FOREIGN KEY (party_id) REFERENCES public.parties(owner_id) ON DELETE SET NULL;


--
-- Name: assessments fk_assessments_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessments
    ADD CONSTRAINT fk_assessments_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;


--
-- Name: businesses fk_businesses_party; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.businesses
    ADD CONSTRAINT fk_businesses_party FOREIGN KEY (id) REFERENCES public.parties(owner_id);


--
-- Name: cards fk_cards_conversation_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cards
    ADD CONSTRAINT fk_cards_conversation_id FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE SET NULL;


--
-- Name: cards fk_cards_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cards
    ADD CONSTRAINT fk_cards_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;


--
-- Name: cic_records fk_cic_records_party_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cic_records
    ADD CONSTRAINT fk_cic_records_party_id FOREIGN KEY (party_id) REFERENCES public.parties(owner_id) ON DELETE SET NULL;


--
-- Name: collaterals fk_collaterals_party_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.collaterals
    ADD CONSTRAINT fk_collaterals_party_id FOREIGN KEY (party_id) REFERENCES public.parties(owner_id) ON DELETE SET NULL;


--
-- Name: conversations fk_conversations_group_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT fk_conversations_group_id FOREIGN KEY (group_id) REFERENCES public.conversation_groups(id) ON DELETE SET NULL;


--
-- Name: conversations fk_conversations_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT fk_conversations_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;


--
-- Name: customers fk_customers_party; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT fk_customers_party FOREIGN KEY (id) REFERENCES public.parties(owner_id);


--
-- Name: employment_records fk_employment_records_party_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employment_records
    ADD CONSTRAINT fk_employment_records_party_id FOREIGN KEY (party_id) REFERENCES public.parties(owner_id) ON DELETE SET NULL;


--
-- Name: external_case_links fk_external_case_links_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.external_case_links
    ADD CONSTRAINT fk_external_case_links_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;


--
-- Name: integration_inbox fk_integration_inbox_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.integration_inbox
    ADD CONSTRAINT fk_integration_inbox_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;


--
-- Name: interaction_notes fk_interaction_notes_party_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interaction_notes
    ADD CONSTRAINT fk_interaction_notes_party_id FOREIGN KEY (party_id) REFERENCES public.parties(owner_id) ON DELETE SET NULL;


--
-- Name: loans fk_loans_party_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.loans
    ADD CONSTRAINT fk_loans_party_id FOREIGN KEY (party_id) REFERENCES public.parties(owner_id) ON DELETE SET NULL;


--
-- Name: messages fk_messages_conversation_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT fk_messages_conversation_id FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE SET NULL;


--
-- Name: messages fk_messages_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT fk_messages_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;


--
-- Name: owner_documents fk_owner_documents_party_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.owner_documents
    ADD CONSTRAINT fk_owner_documents_party_id FOREIGN KEY (party_id) REFERENCES public.parties(owner_id) ON DELETE SET NULL;


--
-- Name: party_relations fk_party_relations_from_party_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.party_relations
    ADD CONSTRAINT fk_party_relations_from_party_id FOREIGN KEY (from_party_id) REFERENCES public.parties(owner_id) ON DELETE SET NULL;


--
-- Name: party_relations fk_party_relations_to_party_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.party_relations
    ADD CONSTRAINT fk_party_relations_to_party_id FOREIGN KEY (to_party_id) REFERENCES public.parties(owner_id) ON DELETE SET NULL;


--
-- Name: police_records fk_police_records_party_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.police_records
    ADD CONSTRAINT fk_police_records_party_id FOREIGN KEY (party_id) REFERENCES public.parties(owner_id) ON DELETE SET NULL;


--
-- Name: shadow_reviews fk_shadow_reviews_approval; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shadow_reviews
    ADD CONSTRAINT fk_shadow_reviews_approval FOREIGN KEY (approval_id) REFERENCES public.approvals(id) NOT VALID;


--
-- Name: shadow_reviews fk_shadow_reviews_conversation_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shadow_reviews
    ADD CONSTRAINT fk_shadow_reviews_conversation_id FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE SET NULL;


--
-- Name: shadow_reviews fk_shadow_reviews_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shadow_reviews
    ADD CONSTRAINT fk_shadow_reviews_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;


--
-- Name: task_attempts fk_task_attempts_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_attempts
    ADD CONSTRAINT fk_task_attempts_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;


--
-- Name: tasks fk_tasks_conversation_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT fk_tasks_conversation_id FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE SET NULL;


--
-- Name: tasks fk_tasks_parent_task; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT fk_tasks_parent_task FOREIGN KEY (parent_task_id) REFERENCES public.tasks(id) ON DELETE SET NULL;


--
-- Name: tasks fk_tasks_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT fk_tasks_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;


--
-- Name: tool_calls fk_tool_calls_conversation_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tool_calls
    ADD CONSTRAINT fk_tool_calls_conversation_id FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE SET NULL;


--
-- Name: tool_calls fk_tool_calls_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tool_calls
    ADD CONSTRAINT fk_tool_calls_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;


--
-- Name: users fk_users_party_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT fk_users_party_id FOREIGN KEY (party_id) REFERENCES public.parties(owner_id) ON DELETE SET NULL;


--
-- Name: users fk_users_tenant_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT fk_users_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT;


--
-- Name: prompt_bindings prompt_bindings_prompt_key_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_bindings
    ADD CONSTRAINT prompt_bindings_prompt_key_version_id_fkey FOREIGN KEY (prompt_key, version_id) REFERENCES public.prompt_versions(prompt_key, id) ON DELETE RESTRICT;


--
-- Name: prompt_versions prompt_versions_prompt_key_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_versions
    ADD CONSTRAINT prompt_versions_prompt_key_fkey FOREIGN KEY (prompt_key) REFERENCES public.prompt_definitions(prompt_key) ON DELETE RESTRICT;


--
-- Name: task_attempts task_attempts_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_attempts
    ADD CONSTRAINT task_attempts_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE SET NULL;


--
-- Name: task_attempts task_attempts_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_attempts
    ADD CONSTRAINT task_attempts_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--

\unrestrict olC8FSwCxYbbqHpWFlyoIbSlcZZJnnj4VfJeJ9ciNbilOjIjCv5qi4g46Ys0aU0
