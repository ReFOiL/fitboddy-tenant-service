from domain.entities import DiscoveryProfile, TrainerClientRelation, TrainerFunnelMetrics
from presentation.http.schemas import DiscoveryProfileResponse, TrainerClientRelationResponse, TrainerFunnelResponse


class TenantResponseFactory:
    @staticmethod
    def from_domain_profile(profile: DiscoveryProfile) -> DiscoveryProfileResponse:
        return DiscoveryProfileResponse(
            user_id=profile.user_id,
            display_name=profile.display_name,
            role=profile.role,
            is_visible=profile.is_visible,
            looking_for_trainer=profile.looking_for_trainer,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )

    @staticmethod
    def from_domain_relation(relation: TrainerClientRelation) -> TrainerClientRelationResponse:
        return TrainerClientRelationResponse(
            relation_id=relation.relation_id,
            trainer_user_id=relation.trainer_user_id,
            client_user_id=relation.client_user_id,
            client_display_name=relation.client_display_name,
            status=relation.status,
            source=relation.source,
            created_at=relation.created_at,
            updated_at=relation.updated_at,
        )

    @staticmethod
    def from_domain_trainer_funnel(metrics: TrainerFunnelMetrics) -> TrainerFunnelResponse:
        return TrainerFunnelResponse(
            trainer_user_id=metrics.trainer_user_id,
            invites_sent=metrics.invites_sent,
            invites_pending=metrics.invites_pending,
            invites_accepted=metrics.invites_accepted,
            invites_declined=metrics.invites_declined,
            active_clients=metrics.active_clients,
            invite_acceptance_rate=metrics.invite_acceptance_rate,
        )
