"""initial schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-11 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        'users',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('telegram_chat_id', sa.String(64), nullable=True),
        sa.Column('timezone', sa.String(64), nullable=False, server_default='Africa/Lagos'),
        sa.Column('mode', sa.String(32), nullable=False, server_default='autopilot'),
        sa.Column('status', sa.String(32), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_telegram_chat_id', 'users', ['telegram_chat_id'])

    # 2. profiles
    op.create_table(
        'profiles',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('user_id', sa.CHAR(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('personal_details', sa.JSON(), nullable=False),
        sa.Column('education_history', sa.JSON(), nullable=False),
        sa.Column('grades', sa.JSON(), nullable=False),
        sa.Column('test_scores', sa.JSON(), nullable=False),
        sa.Column('achievements', sa.JSON(), nullable=False),
        sa.Column('financial_need_info', sa.JSON(), nullable=False),
        sa.Column('target_countries', sa.JSON(), nullable=False),
        sa.Column('target_fields_of_study', sa.JSON(), nullable=False),
        sa.Column('completeness_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_profiles_user_id', 'profiles', ['user_id'], unique=True)

    # 3. documents
    op.create_table(
        'documents',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('user_id', sa.CHAR(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', sa.String(64), nullable=False),
        sa.Column('storage_key', sa.String(512), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('verified', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_documents_user_id', 'documents', ['user_id'])

    # 4. scholarships
    op.create_table(
        'scholarships',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('provider', sa.String(255), nullable=False),
        sa.Column('country', sa.String(128), nullable=False),
        sa.Column('level', sa.String(64), nullable=False),
        sa.Column('field', sa.String(128), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('currency', sa.String(16), nullable=False, server_default='USD'),
        sa.Column('deadline', sa.DateTime(timezone=True), nullable=True),
        sa.Column('eligibility_rules', sa.JSON(), nullable=False),
        sa.Column('application_url', sa.String(1024), nullable=False),
        sa.Column('requires_essay', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('source', sa.String(255), nullable=False, server_default='catalog'),
        sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(32), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_scholarships_deadline', 'scholarships', ['deadline'])

    # 5. matches
    op.create_table(
        'matches',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('user_id', sa.CHAR(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('scholarship_id', sa.CHAR(36), sa.ForeignKey('scholarships.id', ondelete='CASCADE'), nullable=False),
        sa.Column('fit_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('urgency_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('reasons', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_matches_user_id', 'matches', ['user_id'])
    op.create_index('ix_matches_scholarship_id', 'matches', ['scholarship_id'])

    # 6. applications
    op.create_table(
        'applications',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('user_id', sa.CHAR(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('scholarship_id', sa.CHAR(36), sa.ForeignKey('scholarships.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(32), nullable=False, server_default='discovered'),
        sa.Column('mode_used', sa.String(32), nullable=False, server_default='autopilot'),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('confirmation_ref', sa.String(255), nullable=True),
        sa.Column('outcome', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('idx_app_user_status', 'applications', ['user_id', 'status'])
    op.create_index('idx_app_scholarship_id', 'applications', ['scholarship_id'])

    # 7. application_events
    op.create_table(
        'application_events',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('application_id', sa.CHAR(36), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=False),
        sa.Column('actor', sa.String(64), nullable=False),
        sa.Column('event_type', sa.String(64), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_application_events_application_id', 'application_events', ['application_id'])

    # 8. drafts
    op.create_table(
        'drafts',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('application_id', sa.CHAR(36), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kind', sa.String(64), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('source_facts', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_drafts_application_id', 'drafts', ['application_id'])

    # 9. jobs
    op.create_table(
        'jobs',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('type', sa.String(64), nullable=False),
        sa.Column('status', sa.String(32), nullable=False, server_default='pending'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True),
        sa.Column('locked_by', sa.String(128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 10. api_keys
    op.create_table(
        'api_keys',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('user_id', sa.CHAR(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('hashed_key', sa.String(128), nullable=False),
        sa.Column('scopes', sa.JSON(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_api_keys_hashed_key', 'api_keys', ['hashed_key'], unique=True)
    op.create_index('ix_api_keys_user_id', 'api_keys', ['user_id'])

    # 11. webhooks
    op.create_table(
        'webhooks',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('user_id', sa.CHAR(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('url', sa.String(1024), nullable=False),
        sa.Column('secret', sa.String(255), nullable=False),
        sa.Column('events_subscribed', sa.JSON(), nullable=False),
        sa.Column('failure_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_webhooks_user_id', 'webhooks', ['user_id'])


def downgrade() -> None:
    op.drop_table('webhooks')
    op.drop_table('api_keys')
    op.drop_table('jobs')
    op.drop_table('drafts')
    op.drop_table('application_events')
    op.drop_table('applications')
    op.drop_table('matches')
    op.drop_table('scholarships')
    op.drop_table('documents')
    op.drop_table('profiles')
    op.drop_table('users')
