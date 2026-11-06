-- CreateEnum
CREATE TYPE "source_kind" AS ENUM ('api', 'rss', 'html');

-- CreateEnum
CREATE TYPE "crawl_status" AS ENUM ('running', 'ok', 'failed');

-- CreateEnum
CREATE TYPE "seniority" AS ENUM ('intern', 'junior', 'mid', 'senior', 'lead', 'unspecified');

-- CreateEnum
CREATE TYPE "job_type" AS ENUM ('full_time', 'part_time', 'contract', 'freelance', 'unspecified');

-- CreateEnum
CREATE TYPE "work_setup" AS ENUM ('remote', 'hybrid', 'onsite', 'unspecified');

-- CreateEnum
CREATE TYPE "skill_category" AS ENUM ('language', 'framework', 'database', 'tool', 'cloud');

-- CreateTable
CREATE TABLE "sources" (
    "id" SERIAL NOT NULL,
    "slug" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "base_url" TEXT NOT NULL,
    "kind" "source_kind" NOT NULL,
    "is_active" BOOLEAN NOT NULL DEFAULT false,
    "crawl_interval_minutes" INTEGER NOT NULL DEFAULT 1440,
    "last_crawled_at" TIMESTAMPTZ(6),
    "attribution_text" TEXT NOT NULL,
    "terms_url" TEXT,

    CONSTRAINT "sources_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "crawl_runs" (
    "id" SERIAL NOT NULL,
    "source_id" INTEGER NOT NULL,
    "started_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "finished_at" TIMESTAMPTZ(6),
    "status" "crawl_status" NOT NULL DEFAULT 'running',
    "pages_fetched" INTEGER NOT NULL DEFAULT 0,
    "postings_found" INTEGER NOT NULL DEFAULT 0,
    "postings_new" INTEGER NOT NULL DEFAULT 0,
    "error_message" TEXT,

    CONSTRAINT "crawl_runs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "raw_postings" (
    "id" SERIAL NOT NULL,
    "source_id" INTEGER NOT NULL,
    "crawl_run_id" INTEGER,
    "external_id" TEXT NOT NULL,
    "url" TEXT NOT NULL,
    "payload" TEXT NOT NULL,
    "content_hash" CHAR(64) NOT NULL,
    "fetched_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "parsed_at" TIMESTAMPTZ(6),
    "parse_error" TEXT,

    CONSTRAINT "raw_postings_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "companies" (
    "id" SERIAL NOT NULL,
    "name" TEXT NOT NULL,
    "normalized_name" TEXT NOT NULL,

    CONSTRAINT "companies_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "postings" (
    "id" SERIAL NOT NULL,
    "raw_posting_id" INTEGER,
    "source_id" INTEGER NOT NULL,
    "external_id" TEXT NOT NULL,
    "company_id" INTEGER,
    "title" TEXT NOT NULL,
    "title_normalized" TEXT NOT NULL,
    "seniority" "seniority" NOT NULL DEFAULT 'unspecified',
    "job_type" "job_type" NOT NULL DEFAULT 'unspecified',
    "work_setup" "work_setup" NOT NULL DEFAULT 'unspecified',
    "ph_eligible" BOOLEAN,
    "location_text" TEXT,
    "salary_raw" TEXT,
    "salary_currency" CHAR(3),
    "salary_period" TEXT,
    "salary_min_php_monthly" INTEGER,
    "salary_max_php_monthly" INTEGER,
    "description" TEXT,
    "source_url" TEXT NOT NULL,
    "posted_at" TIMESTAMPTZ(6),
    "first_seen_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "last_seen_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "is_active" BOOLEAN NOT NULL DEFAULT true,
    "fingerprint" CHAR(40),
    "canonical_posting_id" INTEGER,

    CONSTRAINT "postings_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "skills" (
    "id" SERIAL NOT NULL,
    "name" TEXT NOT NULL,
    "category" "skill_category" NOT NULL,

    CONSTRAINT "skills_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "skill_aliases" (
    "id" SERIAL NOT NULL,
    "skill_id" INTEGER NOT NULL,
    "pattern" TEXT NOT NULL,
    "requirements_only" BOOLEAN NOT NULL DEFAULT false,

    CONSTRAINT "skill_aliases_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "posting_skills" (
    "posting_id" INTEGER NOT NULL,
    "skill_id" INTEGER NOT NULL,

    CONSTRAINT "posting_skills_pkey" PRIMARY KEY ("posting_id","skill_id")
);

-- CreateTable
CREATE TABLE "exchange_rates" (
    "date" DATE NOT NULL,
    "currency" CHAR(3) NOT NULL,
    "php_per_unit" DECIMAL(14,6) NOT NULL,

    CONSTRAINT "exchange_rates_pkey" PRIMARY KEY ("date","currency")
);

-- CreateTable
CREATE TABLE "daily_skill_stats" (
    "date" DATE NOT NULL,
    "skill_id" INTEGER NOT NULL,
    "active_postings" INTEGER NOT NULL DEFAULT 0,
    "new_postings" INTEGER NOT NULL DEFAULT 0,
    "median_salary_php" INTEGER,

    CONSTRAINT "daily_skill_stats_pkey" PRIMARY KEY ("date","skill_id")
);

-- CreateIndex
CREATE UNIQUE INDEX "sources_slug_key" ON "sources"("slug");

-- CreateIndex
CREATE INDEX "crawl_runs_source_id_started_at_idx" ON "crawl_runs"("source_id", "started_at" DESC);

-- CreateIndex
CREATE INDEX "crawl_runs_started_at_idx" ON "crawl_runs"("started_at");

-- CreateIndex
CREATE INDEX "raw_postings_fetched_at_idx" ON "raw_postings"("fetched_at");

-- CreateIndex
CREATE INDEX "raw_postings_parsed_at_idx" ON "raw_postings"("parsed_at");

-- CreateIndex
CREATE UNIQUE INDEX "raw_postings_source_id_external_id_key" ON "raw_postings"("source_id", "external_id");

-- CreateIndex
CREATE UNIQUE INDEX "companies_normalized_name_key" ON "companies"("normalized_name");

-- CreateIndex
CREATE INDEX "postings_first_seen_at_idx" ON "postings"("first_seen_at");

-- CreateIndex
CREATE INDEX "postings_last_seen_at_idx" ON "postings"("last_seen_at");

-- CreateIndex
CREATE INDEX "postings_is_active_canonical_posting_id_idx" ON "postings"("is_active", "canonical_posting_id");

-- CreateIndex
CREATE INDEX "postings_company_id_first_seen_at_idx" ON "postings"("company_id", "first_seen_at");

-- CreateIndex
CREATE INDEX "postings_fingerprint_first_seen_at_idx" ON "postings"("fingerprint", "first_seen_at");

-- CreateIndex
CREATE INDEX "postings_canonical_posting_id_idx" ON "postings"("canonical_posting_id");

-- CreateIndex
CREATE INDEX "postings_raw_posting_id_idx" ON "postings"("raw_posting_id");

-- CreateIndex
CREATE UNIQUE INDEX "postings_source_id_external_id_key" ON "postings"("source_id", "external_id");

-- CreateIndex
CREATE UNIQUE INDEX "skills_name_key" ON "skills"("name");

-- CreateIndex
CREATE UNIQUE INDEX "skill_aliases_skill_id_pattern_key" ON "skill_aliases"("skill_id", "pattern");

-- CreateIndex
CREATE INDEX "posting_skills_skill_id_idx" ON "posting_skills"("skill_id");

-- CreateIndex
CREATE INDEX "daily_skill_stats_skill_id_date_idx" ON "daily_skill_stats"("skill_id", "date");

-- AddForeignKey
ALTER TABLE "crawl_runs" ADD CONSTRAINT "crawl_runs_source_id_fkey" FOREIGN KEY ("source_id") REFERENCES "sources"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "raw_postings" ADD CONSTRAINT "raw_postings_source_id_fkey" FOREIGN KEY ("source_id") REFERENCES "sources"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "raw_postings" ADD CONSTRAINT "raw_postings_crawl_run_id_fkey" FOREIGN KEY ("crawl_run_id") REFERENCES "crawl_runs"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "postings" ADD CONSTRAINT "postings_raw_posting_id_fkey" FOREIGN KEY ("raw_posting_id") REFERENCES "raw_postings"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "postings" ADD CONSTRAINT "postings_source_id_fkey" FOREIGN KEY ("source_id") REFERENCES "sources"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "postings" ADD CONSTRAINT "postings_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "companies"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "postings" ADD CONSTRAINT "postings_canonical_posting_id_fkey" FOREIGN KEY ("canonical_posting_id") REFERENCES "postings"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "skill_aliases" ADD CONSTRAINT "skill_aliases_skill_id_fkey" FOREIGN KEY ("skill_id") REFERENCES "skills"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "posting_skills" ADD CONSTRAINT "posting_skills_posting_id_fkey" FOREIGN KEY ("posting_id") REFERENCES "postings"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "posting_skills" ADD CONSTRAINT "posting_skills_skill_id_fkey" FOREIGN KEY ("skill_id") REFERENCES "skills"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "daily_skill_stats" ADD CONSTRAINT "daily_skill_stats_skill_id_fkey" FOREIGN KEY ("skill_id") REFERENCES "skills"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- ---------------------------------------------------------------------------
-- Hand-added CHECK constraints (Prisma can't express these in schema.prisma).
-- ---------------------------------------------------------------------------
ALTER TABLE "postings" ADD CONSTRAINT "postings_salary_range_check"
  CHECK ("salary_min_php_monthly" IS NULL OR "salary_max_php_monthly" IS NULL
         OR "salary_min_php_monthly" <= "salary_max_php_monthly");
ALTER TABLE "postings" ADD CONSTRAINT "postings_salary_positive_check"
  CHECK (("salary_min_php_monthly" IS NULL OR "salary_min_php_monthly" > 0)
     AND ("salary_max_php_monthly" IS NULL OR "salary_max_php_monthly" > 0));
ALTER TABLE "postings" ADD CONSTRAINT "postings_salary_period_check"
  CHECK ("salary_period" IS NULL OR "salary_period" IN ('hour', 'day', 'week', 'month', 'year'));
ALTER TABLE "postings" ADD CONSTRAINT "postings_source_url_check" CHECK ("source_url" <> '');
ALTER TABLE "postings" ADD CONSTRAINT "postings_not_self_canonical_check"
  CHECK ("canonical_posting_id" IS NULL OR "canonical_posting_id" <> "id");
ALTER TABLE "postings" ADD CONSTRAINT "postings_seen_order_check" CHECK ("first_seen_at" <= "last_seen_at");
ALTER TABLE "exchange_rates" ADD CONSTRAINT "exchange_rates_positive_check" CHECK ("php_per_unit" > 0);
ALTER TABLE "crawl_runs" ADD CONSTRAINT "crawl_runs_counts_check"
  CHECK ("pages_fetched" >= 0 AND "postings_found" >= 0 AND "postings_new" >= 0);
