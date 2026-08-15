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

    def list_visible_trainers(
        self,
        *,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[DiscoveryProfileModel]:
        statement = (
            select(DiscoveryProfileModel)
            .where(DiscoveryProfileModel.role == "trainer", DiscoveryProfileModel.is_visible.is_(True))
            .order_by(DiscoveryProfileModel.updated_at.desc())
        )
        if limit is not None:
            statement = statement.offset(offset).limit(limit)
        return list(self._session.scalars(statement).all())

    def count_visible_trainers(self) -> int:
        statement = select(func.count(DiscoveryProfileModel.user_id)).where(
            DiscoveryProfileModel.role == "trainer",
            DiscoveryProfileModel.is_visible.is_(True),
        )
        count = self._session.scalar(statement)
        return int(count or 0)

    def list_visible_trainer_ids(self) -> list[str]:
        statement = (
            select(DiscoveryProfileModel.user_id)
            .where(DiscoveryProfileModel.role == "trainer", DiscoveryProfileModel.is_visible.is_(True))
            .order_by(DiscoveryProfileModel.updated_at.desc())
        )
        return list(self._session.scalars(statement).all())

    def list_by_user_ids(self, user_ids: list[str]) -> list[DiscoveryProfileModel]:
        if not user_ids:
            return []
        rows = list(
            self._session.scalars(select(DiscoveryProfileModel).where(DiscoveryProfileModel.user_id.in_(user_ids))).all()
        )
        by_id = {row.user_id: row for row in rows}
        return [by_id[user_id] for user_id in user_ids if user_id in by_id]

    def list_all(
        self,
        *,
        role: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[DiscoveryProfileModel], int]:
        statement = select(DiscoveryProfileModel)
        count_statement = select(func.count(DiscoveryProfileModel.user_id))
        if role:
            statement = statement.where(DiscoveryProfileModel.role == role)
            count_statement = count_statement.where(DiscoveryProfileModel.role == role)
        total = int(self._session.scalar(count_statement) or 0)
        rows = list(
            self._session.scalars(
                statement.order_by(DiscoveryProfileModel.updated_at.desc()).offset(offset).limit(limit)
            ).all()
        )
        return rows, total

    def count_by_role(self, role: str) -> int:
        count = self._session.scalar(
            select(func.count(DiscoveryProfileModel.user_id)).where(DiscoveryProfileModel.role == role)
        )
        return int(count or 0)

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

    def list_by_trainer_statuses(
        self,
        trainer_user_id: str,
        statuses: list[str],
        *,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[TrainerClientRelationModel]:
        statement = (
            select(TrainerClientRelationModel)
            .where(
                TrainerClientRelationModel.trainer_user_id == trainer_user_id,
                TrainerClientRelationModel.status.in_(statuses),
            )
            .order_by(TrainerClientRelationModel.updated_at.desc())
        )
        if limit is not None:
            statement = statement.offset(offset).limit(limit)
        return list(self._session.scalars(statement).all())

    def list_ids_by_trainer_statuses(
        self,
        trainer_user_id: str,
        statuses: list[str],
    ) -> list[tuple[str, str]]:
        statement = (
            select(TrainerClientRelationModel.relation_id, TrainerClientRelationModel.client_user_id)
            .where(
                TrainerClientRelationModel.trainer_user_id == trainer_user_id,
                TrainerClientRelationModel.status.in_(statuses),
            )
            .order_by(TrainerClientRelationModel.updated_at.desc())
        )
        return [(row[0], row[1]) for row in self._session.execute(statement).all()]

    def list_by_ids(self, relation_ids: list[str]) -> list[TrainerClientRelationModel]:
        if not relation_ids:
            return []
        rows = list(
            self._session.scalars(
                select(TrainerClientRelationModel).where(TrainerClientRelationModel.relation_id.in_(relation_ids))
            ).all()
        )
        by_id = {row.relation_id: row for row in rows}
        return [by_id[relation_id] for relation_id in relation_ids if relation_id in by_id]

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

    def list_all(
        self,
        *,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[TrainerClientRelationModel], int]:
        statement = select(TrainerClientRelationModel)
        count_statement = select(func.count(TrainerClientRelationModel.relation_id))
        if status:
            statement = statement.where(TrainerClientRelationModel.status == status)
            count_statement = count_statement.where(TrainerClientRelationModel.status == status)
        total = int(self._session.scalar(count_statement) or 0)
        rows = list(
            self._session.scalars(
                statement.order_by(TrainerClientRelationModel.updated_at.desc()).offset(offset).limit(limit)
            ).all()
        )
        return rows, total

    def count_all(self) -> int:
        count = self._session.scalar(select(func.count(TrainerClientRelationModel.relation_id)))
        return int(count or 0)

    def count_by_status(self, status: str) -> int:
        count = self._session.scalar(
            select(func.count(TrainerClientRelationModel.relation_id)).where(
                TrainerClientRelationModel.status == status
            )
        )
        return int(count or 0)

