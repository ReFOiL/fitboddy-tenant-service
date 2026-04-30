from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from application.errors import RelationConflictError
from application.models import DiscoveryProfileModel, TrainerClientRelationModel


class DiscoveryProfileRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_id(self, user_id: str) -> DiscoveryProfileModel | None:
        return self._session.get(DiscoveryProfileModel, user_id)

    def upsert(self, profile: DiscoveryProfileModel) -> DiscoveryProfileModel:
        existing = self.find_by_id(profile.user_id)
        if existing is None:
            self._session.add(profile)
            self._session.flush()
            return profile

        existing.role = profile.role
        existing.is_visible = profile.is_visible
        existing.looking_for_trainer = profile.looking_for_trainer
        existing.updated_at = profile.updated_at
        self._session.flush()
        return existing

    def list_visible_trainers(self) -> list[DiscoveryProfileModel]:
        statement = (
            select(DiscoveryProfileModel)
            .where(DiscoveryProfileModel.role == "trainer", DiscoveryProfileModel.is_visible.is_(True))
            .order_by(DiscoveryProfileModel.updated_at.desc())
        )
        return list(self._session.scalars(statement).all())

    def list_clients_looking_for_trainer(self) -> list[DiscoveryProfileModel]:
        statement = (
            select(DiscoveryProfileModel)
            .where(DiscoveryProfileModel.role == "client", DiscoveryProfileModel.looking_for_trainer.is_(True))
            .order_by(DiscoveryProfileModel.updated_at.desc())
        )
        return list(self._session.scalars(statement).all())


class TrainerClientRelationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, relation: TrainerClientRelationModel) -> TrainerClientRelationModel:
        self._session.add(relation)
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise RelationConflictError("relation already exists between trainer and client") from exc
        return relation

    def find_by_id(self, relation_id: str) -> TrainerClientRelationModel | None:
        return self._session.get(TrainerClientRelationModel, relation_id)

    def find_by_pair(self, trainer_user_id: str, client_user_id: str) -> TrainerClientRelationModel | None:
        statement = select(TrainerClientRelationModel).where(
            TrainerClientRelationModel.trainer_user_id == trainer_user_id,
            TrainerClientRelationModel.client_user_id == client_user_id,
        )
        return self._session.scalar(statement)

    def find_active_by_client(self, client_user_id: str) -> TrainerClientRelationModel | None:
        statement = select(TrainerClientRelationModel).where(
            TrainerClientRelationModel.client_user_id == client_user_id,
            TrainerClientRelationModel.status == "active",
        )
        return self._session.scalar(statement)

    def list_by_trainer(self, trainer_user_id: str, status: str) -> list[TrainerClientRelationModel]:
        statement = (
            select(TrainerClientRelationModel)
            .where(
                TrainerClientRelationModel.trainer_user_id == trainer_user_id,
                TrainerClientRelationModel.status == status,
            )
            .order_by(TrainerClientRelationModel.updated_at.desc())
        )
        return list(self._session.scalars(statement).all())

    def list_by_trainer_statuses(self, trainer_user_id: str, statuses: list[str]) -> list[TrainerClientRelationModel]:
        statement = (
            select(TrainerClientRelationModel)
            .where(
                TrainerClientRelationModel.trainer_user_id == trainer_user_id,
                TrainerClientRelationModel.status.in_(statuses),
            )
            .order_by(TrainerClientRelationModel.updated_at.desc())
        )
        return list(self._session.scalars(statement).all())

    def list_incoming_invites(self, client_user_id: str) -> list[TrainerClientRelationModel]:
        statement = (
            select(TrainerClientRelationModel)
            .where(
                TrainerClientRelationModel.client_user_id == client_user_id,
                TrainerClientRelationModel.status == "invited",
            )
            .order_by(TrainerClientRelationModel.updated_at.desc())
        )
        return list(self._session.scalars(statement).all())

    def count_by_trainer_statuses(
        self,
        trainer_user_id: str,
        statuses: list[str],
        source: str | None = None,
    ) -> int:
        statement = select(func.count(TrainerClientRelationModel.relation_id)).where(
            TrainerClientRelationModel.trainer_user_id == trainer_user_id,
            TrainerClientRelationModel.status.in_(statuses),
        )
        if source is not None:
            statement = statement.where(TrainerClientRelationModel.source == source)
        count = self._session.scalar(statement)
        return int(count or 0)
