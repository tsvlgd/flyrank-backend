from sqlalchemy import Boolean, Column, DateTime, Index, Integer, MetaData, String, Table, func

metadata = MetaData()

tasks_table = Table(
    "tasks",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("title", String, nullable=False, unique=True),
    Column("done", Boolean, nullable=False, default=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
)

Index("ix_tasks_done", tasks_table.c.done)

