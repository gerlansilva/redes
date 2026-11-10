"""Esquema do `.scimat` do SciMAT, copiado do fork Bibliomapa.

As instruções foram extraídas de um projeto real (``relime.scimat``) para que
um arquivo gravado pelo Python possa ser aberto no programa Java sem nenhuma
conversão: 25 tabelas, 54 índices e 34 gatilhos. Os gatilhos mantêm os
contadores desnormalizados que o fork consulta (documentos por autor, por
palavra, por referência, etc.), de modo que a importação não precisa calculá-los
à mão.

A versão gravada é ``v1_03``, a única que ``checkKnowledgeBaseStructure``
aceita.
"""

from __future__ import annotations

import sqlite3

VERSAO = "v1_03"

INSTRUCOES = r"""
CREATE TABLE Affiliation(
  idAffiliation INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL CHECK(idAffiliation>=0),
  fullAffiliation VARCHAR NOT NULL UNIQUE,
  affiliation_documentsCount INTEGER CHECK(affiliation_documentsCount>=0) DEFAULT 0,
  affiliation_authorsCount INTEGER CHECK(affiliation_authorsCount>=0) DEFAULT 0
);

CREATE TABLE Author(
  idAuthor INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL CHECK(idAuthor>=0),
  authorName VARCHAR NOT NULL,
  fullAuthorName VARCHAR NOT NULL,
  author_documentsCount INTEGER CHECK(author_documentsCount>=0) DEFAULT 0,
  author_affiliationsCount INTEGER CHECK(author_affiliationsCount>=0) DEFAULT 0,
  AuthorGroup_idAuthorGroup INTEGER CHECK(AuthorGroup_idAuthorGroup>=0),
  CONSTRAINT author_UNIQUE
     UNIQUE(authorName,fullAuthorName),
  CONSTRAINT fk_Author_AuthorGroup
     FOREIGN KEY(AuthorGroup_idAuthorGroup)
     REFERENCES AuthorGroup(idAuthorGroup)
     ON DELETE SET NULL
     ON UPDATE CASCADE
);

CREATE TABLE AuthorGroup(
  idAuthorGroup INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL CHECK(idAuthorGroup>=0),
  groupName VARCHAR NOT NULL UNIQUE,
  stopGroup BOOLEAN DEFAULT FALSE,
  itemsCount INTEGER CHECK(itemsCount>=0) DEFAULT 0,
  authorGroup_documentsCount INTEGER CHECK(authorGroup_documentsCount>=0) DEFAULT 0
);

CREATE TABLE AuthorReference(
  idAuthorReference INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL CHECK(idAuthorReference>=0),
  authorName VARCHAR NOT NULL UNIQUE,
  authorReference_referencesCount INTEGER CHECK(authorReference_referencesCount>=0) DEFAULT 0,
  authorReference_documentsCount INTEGER CHECK(authorReference_documentsCount>=0) DEFAULT 0,
  AuthorReferenceGroup_idAuthorReferenceGroup INTEGER CHECK(AuthorReferenceGroup_idAuthorReferenceGroup>=0),
  Author_idAuthor INTEGER UNIQUE CHECK(Author_idAuthor>=0),
  CONSTRAINT fk_AuthorReference_AuthorReferenceGroup
     FOREIGN KEY(AuthorReferenceGroup_idAuthorReferenceGroup)
     REFERENCES AuthorReferenceGroup(idAuthorReferenceGroup)
     ON DELETE SET NULL
     ON UPDATE CASCADE,
  CONSTRAINT fk_AuthorReference_Author
     FOREIGN KEY(Author_idAuthor)
     REFERENCES Author(idAuthor)
     ON DELETE SET NULL
     ON UPDATE CASCADE
);

CREATE TABLE AuthorReferenceGroup(
  idAuthorReferenceGroup INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL CHECK(idAuthorReferenceGroup>=0),
  groupName VARCHAR NOT NULL UNIQUE,
  stopGroup BOOLEAN DEFAULT FALSE,
  itemsCount INTEGER CHECK(itemsCount>=0) DEFAULT 0,
  authorReferenceGroup_documentsCount INTEGER CHECK(authorReferenceGroup_documentsCount>=0) DEFAULT 0
);

CREATE TABLE AuthorReference_Reference(
  AuthorReference_idAuthorReference INTEGER NOT NULL CHECK(AuthorReference_idAuthorReference>=0),
  Reference_idReference INTEGER NOT NULL CHECK(Reference_idReference>=0),
  position INTEGER CHECK(position >= 1),
  PRIMARY KEY(AuthorReference_idAuthorReference,Reference_idReference),
  CONSTRAINT fk_AuthorReference_Reference_AuthorReference
     FOREIGN KEY(AuthorReference_idAuthorReference)
     REFERENCES AuthorReference(idAuthorReference)
     ON DELETE CASCADE
     ON UPDATE CASCADE,
  CONSTRAINT fk_AuthorReference_Reference_Reference
     FOREIGN KEY(Reference_idReference)
     REFERENCES Reference(idReference)
     ON DELETE CASCADE
     ON UPDATE CASCADE
);

CREATE TABLE Author_Affiliation(
  Affiliation_idAffiliation INTEGER NOT NULL CHECK(Affiliation_idAffiliation>=0),
  Author_idAuthor INTEGER NOT NULL CHECK(Author_idAuthor>=0),
  PRIMARY KEY(Affiliation_idAffiliation,Author_idAuthor),
  CONSTRAINT fk_AffiliationAuthor_Affiliation
     FOREIGN KEY(Affiliation_idAffiliation)
     REFERENCES Affiliation(idAffiliation)
     ON DELETE CASCADE
     ON UPDATE CASCADE,
  CONSTRAINT fk_AffiliationAuthor_Author
     FOREIGN KEY(Author_idAuthor)
     REFERENCES Author(idAuthor)
     ON DELETE CASCADE
     ON UPDATE CASCADE
);

CREATE TABLE Document(
  idDocument INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL CHECK(idDocument>=0),
  title VARCHAR NOT NULL,
  type VARCHAR,
  docAbstract VARCHAR,
  volume VARCHAR,
  issue VARCHAR,
  beginPage VARCHAR,
  endPage VARCHAR,
  citationsCount INTEGER CHECK(citationsCount>=0) DEFAULT 0,
  doi VARCHAR,
  sourceIdentifier VARCHAR,
  document_wordsCount INTEGER CHECK(document_wordsCount>=0) DEFAULT 0,
  authorWordsCount INTEGER CHECK(authorWordsCount>=0) DEFAULT 0,
  sourceWordsCount INTEGER CHECK(sourceWordsCount>=0) DEFAULT 0,
  addedWordsCount INTEGER CHECK(addedWordsCount>=0) DEFAULT 0,
  document_affiliationsCount INTEGER CHECK(document_affiliationsCount>=0) DEFAULT 0,
  document_referencesCount INTEGER CHECK(document_referencesCount>=0) DEFAULT 0,
  year VARCHAR DEFAULT NULL,
  authors VARCHAR DEFAULT NULL,
  PublishDate_idPublishDate INTEGER CHECK(PublishDate_idPublishDate>=0),
  Journal_idJournal INTEGER CHECK(Journal_idJournal>=0),
  CONSTRAINT fk_Document_PublishDate
     FOREIGN KEY(PublishDate_idPublishDate)
     REFERENCES PublishDate(idPublishDate)
     ON DELETE SET NULL
     ON UPDATE CASCADE,
  CONSTRAINT fk_Document_Journal
     FOREIGN KEY(Journal_idJournal)
     REFERENCES Journal(idJournal)
     ON DELETE SET NULL
     ON UPDATE CASCADE
);

CREATE TABLE Document_Affiliation(
  Affiliation_idAffiliation INTEGER NOT NULL CHECK(Affiliation_idAffiliation>=0),
  Document_idDocument INTEGER NOT NULL CHECK(Document_idDocument>=0),
  PRIMARY KEY(Affiliation_idAffiliation,Document_idDocument),
  CONSTRAINT fk_DocumentAffiliation_Affiliation
     FOREIGN KEY(Affiliation_idAffiliation)
     REFERENCES Affiliation(idAffiliation)
     ON DELETE CASCADE
     ON UPDATE CASCADE,
  CONSTRAINT fk_DocumentAffiliation_Document
     FOREIGN KEY(Document_idDocument)
     REFERENCES Document(idDocument)
     ON DELETE CASCADE
     ON UPDATE CASCADE
);

CREATE TABLE Document_Author(
  Author_idAuthor INTEGER NOT NULL CHECK(Author_idAuthor>=0),
  Document_idDocument INTEGER NOT NULL CHECK(Document_idDocument>=0),
  position INTEGER CHECK(position >= 1),
  PRIMARY KEY(Author_idAuthor,Document_idDocument),
  CONSTRAINT fk_DocumentAuthor_Author
     FOREIGN KEY(Author_idAuthor)
     REFERENCES Author(idAuthor)
     ON DELETE CASCADE
     ON UPDATE CASCADE,
  CONSTRAINT fk_DocumentAuthor_Document
     FOREIGN KEY(Document_idDocument)
     REFERENCES Document(idDocument)
     ON DELETE CASCADE
     ON UPDATE CASCADE
);

CREATE TABLE Document_Reference(
  Reference_idReference INTEGER NOT NULL CHECK(Reference_idReference>=0),
  Document_idDocument INTEGER NOT NULL CHECK(Document_idDocument>=0),
  PRIMARY KEY(Reference_idReference,Document_idDocument),
  CONSTRAINT fk_DocumentReference_Reference
     FOREIGN KEY(Reference_idReference)
     REFERENCES Reference(idReference)
     ON DELETE CASCADE
     ON UPDATE CASCADE,
  CONSTRAINT fk_DocumentReference_Document
     FOREIGN KEY(Document_idDocument)
     REFERENCES Document(idDocument)
     ON DELETE CASCADE
     ON UPDATE CASCADE
);

CREATE TABLE Document_Word(
  Document_idDocument INTEGER NOT NULL CHECK(Document_idDocument>=0),
  Word_idWord INTEGER NOT NULL CHECK(Word_idWord>=0),
  isAuthorWord BOOLEAN DEFAULT FALSE,
  isSourceWord BOOLEAN DEFAULT FALSE,
  isAddedWord BOOLEAN DEFAULT FALSE,
  PRIMARY KEY(Document_idDocument,Word_idWord),
  CONSTRAINT fk_DocumentWord_Document
     FOREIGN KEY(Document_idDocument)
     REFERENCES Document(idDocument)
     ON DELETE CASCADE
     ON UPDATE CASCADE,
  CONSTRAINT fk_DocumentWord_Word
     FOREIGN KEY(Word_idWord)
     REFERENCES Word(idWord)
     ON DELETE CASCADE
     ON UPDATE CASCADE
);

CREATE TABLE Journal(
  idJournal INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL CHECK(idJournal>=0),
  source VARCHAR NOT NULL UNIQUE,
  conferenceInformation VARCHAR,
  journal_documentsCount INTEGER CHECK(journal_documentsCount>=0) DEFAULT 0
);

CREATE TABLE Journal_SubjectCategory_PublishDate(
  Journal_idJournal INTEGER NOT NULL CHECK(Journal_idJournal>=0),
  SubjectCategory_idSubjectCategory INTEGER NOT NULL CHECK(SubjectCategory_idSubjectCategory>=0),
  PublishDate_idPublishDate INTEGER NOT NULL CHECK(PublishDate_idPublishDate>=0),
  PRIMARY KEY(Journal_idJournal,SubjectCategory_idSubjectCategory,PublishDate_idPublishDate),
  CONSTRAINT fk_JournalSubjectCategoryPublishDate_Journal
     FOREIGN KEY(Journal_idJournal)
     REFERENCES Journal(idJournal)
     ON DELETE CASCADE
     ON UPDATE CASCADE,
  CONSTRAINT fk_JournalSubjectCategoryPublishDate_SubjectCategory
     FOREIGN KEY(SubjectCategory_idSubjectCategory)
     REFERENCES SubjectCategory(idSubjectCategory)
     ON DELETE CASCADE
     ON UPDATE CASCADE,
  CONSTRAINT fk_JournalSubjectCategoryPublishDate_PublishDate
     FOREIGN KEY(PublishDate_idPublishDate)
     REFERENCES PublishDate(idPublishDate)
     ON DELETE CASCADE
     ON UPDATE CASCADE
);

CREATE TABLE KnowledgeBaseVersion(knowledgeBaseVersion VARCHAR NOT NULL);

CREATE TABLE Period(
  idPeriod INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL CHECK(idPeriod>=0),
  name VARCHAR NOT NULL UNIQUE,
  position INTEGER CHECK(position > 0) DEFAULT 0,
  period_documentsCount INTEGER CHECK(period_documentsCount>=-1) DEFAULT 0,
  period_publishDatesCount INTEGER CHECK(period_publishDatesCount>=0) DEFAULT 0
);

CREATE TABLE PublishDate(
  idPublishDate INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL CHECK(idPublishDate>=0),
  year VARCHAR NOT NULL,
  date VARCHAR NOT NULL,
  publishDate_documentsCount INTEGER CHECK(publishDate_documentsCount>=0) DEFAULT 0,
  CONSTRAINT publishDate_UNIQUE
     UNIQUE(year,date)
);

CREATE TABLE PublishDate_Period(
  PublishDate_idPublishDate INTEGER NOT NULL CHECK(PublishDate_idPublishDate>=0),
  Period_idPeriod INTEGER NOT NULL CHECK(Period_idPeriod>=0),
  PRIMARY KEY(PublishDate_idPublishDate,Period_idPeriod),
  CONSTRAINT fk_PublishDatePeriod_PublishDate
     FOREIGN KEY(PublishDate_idPublishDate)
     REFERENCES PublishDate(idPublishDate)
     ON DELETE CASCADE
     ON UPDATE CASCADE,
  CONSTRAINT fk_PublishDatePeriod_Period
     FOREIGN KEY(Period_idPeriod)
     REFERENCES Period(idPeriod)
     ON DELETE CASCADE
     ON UPDATE CASCADE
);

CREATE TABLE Reference(
  idReference INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL CHECK(idReference>=0),
  fullReference VARCHAR NOT NULL UNIQUE,
  ReferenceSource_idReferenceSource INTEGER,
  volume VARCHAR,
  issue VARCHAR,
  page VARCHAR,
  doi VARCHAR,
  format VARCHAR,
  year VARCHAR,
  reference_documentsCount INTEGER CHECK(reference_documentsCount>=0) DEFAULT 0,
  ReferenceGroup_idReferenceGroup INTEGER CHECK(ReferenceGroup_idReferenceGroup>=0),
  CONSTRAINT fk_Reference_ReferenceSource
     FOREIGN KEY(ReferenceSource_idReferenceSource)
     REFERENCES ReferenceSource(idReferenceSource)
     ON DELETE SET NULL
     ON UPDATE CASCADE,
  CONSTRAINT fk_Reference_ReferenceGroup
     FOREIGN KEY(ReferenceGroup_idReferenceGroup)
     REFERENCES ReferenceGroup(idReferenceGroup)
     ON DELETE SET NULL
     ON UPDATE CASCADE
);

CREATE TABLE ReferenceGroup(
  idReferenceGroup INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL CHECK(idReferenceGroup>=0),
  groupName VARCHAR NOT NULL UNIQUE,
  stopGroup BOOLEAN DEFAULT FALSE,
  itemsCount INTEGER CHECK(itemsCount>=0) DEFAULT 0,
  referenceGroup_documentsCount INTEGER CHECK(referenceGroup_documentsCount>=0) DEFAULT 0
);

CREATE TABLE ReferenceSource(
  idReferenceSource INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL CHECK(idReferenceSource>=0),
  source VARCHAR NOT NULL UNIQUE,
  referenceSource_referencesCount INTEGER CHECK(referenceSource_referencesCount>=0) DEFAULT 0,
  referenceSource_documentsCount INTEGER CHECK(referenceSource_documentsCount>=0) DEFAULT 0,
  ReferenceSourceGroup_idReferencesourceGroup INTEGER CHECK(ReferenceSourceGroup_idReferenceSourceGroup>=0),
  CONSTRAINT fk_Reference_ReferenceSourceGroup
     FOREIGN KEY(ReferenceSourceGroup_idReferencesourceGroup)
     REFERENCES ReferenceSourceGroup(idReferenceSourceGroup)
     ON DELETE SET NULL
     ON UPDATE CASCADE
);

CREATE TABLE ReferenceSourceGroup(
  idReferenceSourceGroup INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL CHECK(idReferenceSourceGroup>=0),
  groupName VARCHAR NOT NULL UNIQUE,
  stopGroup BOOLEAN DEFAULT FALSE,
  itemsCount INTEGER CHECK(itemsCount>=0) DEFAULT 0,
  referenceSourceGroup_documentsCount INTEGER CHECK(referenceSourceGroup_documentsCount>=0) DEFAULT 0
);

CREATE TABLE SubjectCategory(
  idSubjectCategory INTEGER PRIMARY KEY NOT NULL CHECK(idSubjectCategory>=0),
  subjectCategoryName VARCHAR NOT NULL UNIQUE,
  subjectCategory_documentsCount INTEGER CHECK(subjectCategory_documentsCount>=0) DEFAULT 0,
  subjectCategory_journalsCount INTEGER CHECK(subjectCategory_journalsCount>=0) DEFAULT 0);

CREATE TABLE Word(
  idWord INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL CHECK(idWord>=0),
  wordName VARCHAR NOT NULL UNIQUE,
  WordGroup_idWordGroup INTEGER CHECK(WordGroup_idWordGroup>=0),
  word_documentsCount INTEGER CHECK(word_documentsCount>=0) DEFAULT 0,
  roleAuthorCount INTEGER CHECK(roleAuthorCount>=0) DEFAULT 0,
  roleSourceCount INTEGER CHECK(roleSourceCount>=0) DEFAULT 0,
  roleAddedCount INTEGER CHECK(roleAddedCount>=0) DEFAULT 0,
  CONSTRAINT fk_Word_WordGroup
     FOREIGN KEY(WordGroup_idWordGroup)
     REFERENCES WordGroup(idWordGroup)
     ON DELETE SET NULL
     ON UPDATE CASCADE
);

CREATE TABLE WordGroup(
  idWordGroup INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL CHECK(idWordGroup>=0),
  groupName VARCHAR NOT NULL UNIQUE,
  stopGroup BOOLEAN DEFAULT FALSE,
  itemsCount INTEGER CHECK(itemsCount>=0) DEFAULT 0,
  wordGroup_documentsCount INTEGER CHECK(wordGroup_documentsCount>=0) DEFAULT 0
);

CREATE UNIQUE INDEX fk_AffiliationAuthor ON Author_Affiliation(Affiliation_idAffiliation, Author_idAuthor);

CREATE INDEX fk_AffiliationAuthor_Affiliation ON Author_Affiliation(Affiliation_idAffiliation);

CREATE INDEX fk_AffiliationAuthor_Author ON Author_Affiliation(Author_idAuthor);

CREATE UNIQUE INDEX fk_AuthorReference_Author ON AuthorReference(Author_idAuthor);

CREATE INDEX fk_AuthorReference_AuthorReferenceGroup ON AuthorReference(AuthorReferenceGroup_idAuthorReferenceGroup);

CREATE UNIQUE INDEX fk_AuthorReference_Reference ON AuthorReference_Reference(Reference_idReference, AuthorReference_idAuthorReference);

CREATE INDEX fk_AuthorReference_Reference_AuthorReference ON AuthorReference_Reference(AuthorReference_idAuthorReference);

CREATE INDEX fk_AuthorReference_Reference_Reference ON AuthorReference_Reference(Reference_idReference);

CREATE INDEX fk_Author_AuthorGroup ON Author(AuthorGroup_idAuthorGroup);

CREATE UNIQUE INDEX fk_DocumentAffiliation ON Document_Affiliation(Affiliation_idAffiliation, Document_idDocument);

CREATE INDEX fk_DocumentAffiliation_Affiliation ON Document_Affiliation(Affiliation_idAffiliation);

CREATE INDEX fk_DocumentAffiliation_Document ON Document_Affiliation(Document_idDocument);

CREATE UNIQUE INDEX fk_DocumentAuthor ON Document_Author(Document_idDocument, Author_idAuthor);

CREATE INDEX fk_DocumentAuthor_Author ON Document_Author(Author_idAuthor);

CREATE INDEX fk_DocumentAuthor_Document ON Document_Author(Document_idDocument);

CREATE UNIQUE INDEX fk_DocumentWord ON Document_Word(Document_idDocument, Word_idWord);

CREATE INDEX fk_DocumentWord_Document ON Document_Word(Document_idDocument);

CREATE INDEX fk_DocumentWord_Word ON Document_Word(Word_idWord);

CREATE INDEX fk_Document_Journal ON Document(Journal_idJournal);

CREATE INDEX fk_Document_Journal_full ON Document(idDocument, Journal_idJournal);

CREATE INDEX fk_Document_PublishDate ON Document(PublishDate_idPublishDate);

CREATE UNIQUE INDEX fk_JournalSubjectCategoryPublishDate ON Journal_SubjectCategory_PublishDate(SubjectCategory_idSubjectCategory, PublishDate_idPublishDate, Journal_idJournal);

CREATE INDEX fk_JournalSubjectCategoryPublishDate_Journal ON Journal_SubjectCategory_PublishDate(Journal_idJournal);

CREATE INDEX fk_JournalSubjectCategoryPublishDate_PublishDate ON Journal_SubjectCategory_PublishDate(PublishDate_idPublishDate);

CREATE INDEX fk_JournalSubjectCategoryPublishDate_SubjectCategory ON Journal_SubjectCategory_PublishDate(SubjectCategory_idSubjectCategory);

CREATE INDEX fk_JournalSubjectCategoryPublishDate_partial1 ON Journal_SubjectCategory_PublishDate(Journal_idJournal, SubjectCategory_idSubjectCategory);

CREATE INDEX fk_JournalSubjectCategoryPublishDate_partial2 ON Journal_SubjectCategory_PublishDate(SubjectCategory_idSubjectCategory, PublishDate_idPublishDate);

CREATE INDEX fk_JournalSubjectCategoryPublishDate_partial3 ON Journal_SubjectCategory_PublishDate(PublishDate_idPublishDate, Journal_idJournal);

CREATE UNIQUE INDEX fk_PublishDatePeriod ON PublishDate_Period(Period_idPeriod, PublishDate_idPublishDate);

CREATE INDEX fk_PublishDatePeriod_Period ON PublishDate_Period(Period_idPeriod);

CREATE INDEX fk_PublishDatePeriod_PublishDate ON PublishDate_Period(PublishDate_idPublishDate);

CREATE UNIQUE INDEX fk_ReferenceDocument ON Document_Reference(Document_idDocument, Reference_idReference);

CREATE INDEX fk_ReferenceDocument_Document ON Document_Reference(Document_idDocument);

CREATE INDEX fk_ReferenceDocument_Reference ON Document_Reference(Reference_idReference);

CREATE INDEX fk_ReferenceSource_ReferenceSourceGroup ON ReferenceSource(ReferenceSourceGroup_idReferenceSourceGroup);

CREATE INDEX fk_Reference_ReferenceGroup ON Reference(ReferenceGroup_idReferenceGroup);

CREATE INDEX fk_Reference_ReferenceSource ON Reference(ReferenceSource_idReferenceSource);

CREATE INDEX fk_Word_WordGroup ON Word(WordGroup_idWordGroup);

CREATE UNIQUE INDEX idx_Affiliation_pk ON Affiliation(idAffiliation);

CREATE UNIQUE INDEX idx_AuthorGroup_pk ON AuthorGroup(idAuthorGroup);

CREATE UNIQUE INDEX idx_AuthorReferenceGroup_pk ON AuthorReferenceGroup(idAuthorReferenceGroup);

CREATE UNIQUE INDEX idx_AuthorReference_pk ON AuthorReference(idAuthorReference);

CREATE UNIQUE INDEX idx_Author_pk ON Author(idAuthor);

CREATE UNIQUE INDEX idx_Document_pk ON Document(idDocument);

CREATE UNIQUE INDEX idx_Journal_pk ON Journal(idJournal);

CREATE UNIQUE INDEX idx_Period_pk ON Period(idPeriod);

CREATE UNIQUE INDEX idx_PublishDate_pk ON PublishDate(idPublishDate);

CREATE UNIQUE INDEX idx_ReferenceGroup_pk ON ReferenceGroup(idReferenceGroup);

CREATE UNIQUE INDEX idx_ReferenceSourceGroup_pk ON ReferenceSourceGroup(idReferenceSourceGroup);

CREATE UNIQUE INDEX idx_ReferenceSource_pk ON ReferenceSource(idReferenceSource);

CREATE UNIQUE INDEX idx_Reference_pk ON Reference(idReference);

CREATE UNIQUE INDEX idx_SubjectCategory_pk ON SubjectCategory(idSubjectCategory);

CREATE UNIQUE INDEX idx_WordGroup_pk ON WordGroup(idWordGroup);

CREATE UNIQUE INDEX idx_Word_pk ON Word(idWord);

CREATE TRIGGER aggregateData_delete_Author AFTER DELETE ON Author FOR EACH ROW
  BEGIN
    UPDATE AuthorGroup
      SET itemsCount = itemsCount - 1,
          authorGroup_documentsCount = (SELECT COUNT (DISTINCT da.Document_idDocument)
                                        FROM AuthorGroup ag, Author a, Document_Author da
                                        WHERE ag.idAuthorGroup = AuthorGroup.idAuthorGroup AND
                                             ag.idAuthorGroup = a.AuthorGroup_idAuthorGroup AND
                                             a.idAuthor = da.Author_idAuthor)
      WHERE idAuthorGroup = old.AuthorGroup_idAuthorGroup;
  END;

CREATE TRIGGER aggregateData_delete_AuthorReference AFTER DELETE ON AuthorReference FOR EACH ROW
  BEGIN
    UPDATE AuthorReferenceGroup
      SET itemsCount = itemsCount - 1,
          authorReferenceGroup_documentsCount = (SELECT COUNT (DISTINCT dr.Document_idDocument)
                                                 FROM AuthorReferenceGroup arg, AuthorReference ar, AuthorReference_Reference arr, Reference r, Document_Reference dr
                                                 WHERE arg.idAuthorReferenceGroup = AuthorReferenceGroup.idAuthorReferenceGroup AND
                                                       arg.idAuthorReferenceGroup = ar.AuthorReferenceGroup_idAuthorReferenceGroup AND
                                                       ar.idAuthorReference = arr.AuthorReference_idAuthorReference AND
                                                       arr.Reference_idReference = r.idReference AND
                                                       r.idReference = dr.Reference_idReference)
      WHERE idAuthorReferenceGroup = old.AuthorReferenceGroup_idAuthorReferenceGroup;
  END;

CREATE TRIGGER aggregateData_delete_AuthorReference_Reference AFTER DELETE ON AuthorReference_Reference FOR EACH ROW
  BEGIN
    UPDATE AuthorReference
      SET authorReference_referencesCount = authorReference_referencesCount - 1,
          authorReference_documentsCount = (SELECT count(DISTINCT dr.Document_idDocument)
                                            FROM AuthorReference ar, AuthorReference_Reference arr, Reference r, Document_Reference dr
                                            WHERE ar.idAuthorReference = AuthorReference.idAuthorReference AND
                                                  ar.idAuthorReference = arr.AuthorReference_idAuthorReference AND
                                                  arr.Reference_idReference = r.idReference AND
                                                  r.idReference = dr.Reference_idReference)
      WHERE idAuthorReference = old.AuthorReference_idAuthorReference;
    UPDATE AuthorReferenceGroup
      SET authorReferenceGroup_documentsCount = (SELECT COUNT(DISTINCT dr.Document_idDocument) 
                                                 FROM AuthorReferenceGroup arg, AuthorReference ar, AuthorReference_Reference arr, Reference r, Document_Reference dr 
                                                 WHERE arg.idAuthorReferenceGroup =  AuthorReferenceGroup.idAuthorReferenceGroup AND
                                                       arg.idAuthorReferenceGroup = ar.AuthorReferenceGroup_idAuthorReferenceGroup AND
                                                       ar.idAuthorReference = arr.AuthorReference_idAuthorReference AND
                                                       arr.Reference_idReference = r.idReference AND
                                                       r.idReference = dr.Reference_idReference)
      WHERE idAuthorReferenceGroup = (SELECT AuthorReferenceGroup_idAuthorReferenceGroup FROM AuthorReference WHERE idAuthorReference = old.AuthorReference_idAuthorReference);
  END;

CREATE TRIGGER aggregateData_delete_Author_Affiliation AFTER DELETE ON Author_Affiliation FOR EACH ROW
  BEGIN
    UPDATE Affiliation
      SET affiliation_authorsCount = affiliation_authorsCount - 1
      WHERE idAffiliation = old.Affiliation_idAffiliation;
    UPDATE Author
      SET author_affiliationsCount = author_affiliationsCount - 1
      WHERE idAuthor = old.Author_idAuthor;
  END;

CREATE TRIGGER aggregateData_delete_Document AFTER DELETE ON Document FOR EACH ROW
  BEGIN
    UPDATE Journal
      SET journal_documentsCount = journal_documentsCount - 1
      WHERE idJournal = old.Journal_idJournal;
    UPDATE PublishDate
      SET publishDate_documentsCount = publishDate_documentsCount - 1
      WHERE idPublishDate = old.PublishDate_idPublishDate;
    UPDATE Period
      SET period_documentsCount = (SELECT count(d.idDocument)
                                   FROM Period p, PublishDate_Period pup, PublishDate pu, Document d
                                   WHERE p.idPeriod = Period.idPeriod AND
                                         p.idPeriod = pup.Period_idPeriod AND
                                         pup.PublishDate_idPublishDate = pu.idPublishDate AND
                                         pu.idPublishDate = d.PublishDate_idPublishDate)
      WHERE idPeriod IN (SELECT p.idPeriod
                         FROM Period p, PublishDate_Period pup, PublishDate pu
                         WHERE pu.idPublishDate = old.PublishDate_idPublishDate AND
                               p.idPeriod = pup.Period_idPeriod AND
                               pup.PublishDate_idPublishDate = pu.idPublishDate);
    UPDATE SubjectCategory
      SET subjectCategory_documentsCount = (SELECT count(DISTINCT d.idDocument)
                                            FROM SubjectCategory sc, Journal_SubjectCategory_PublishDate jsp, Journal j, Document d
                                            WHERE sc.idSubjectCategory = SubjectCategory.idSubjectCategory AND
                                                  sc.idSubjectCategory = jsp.SubjectCategory_idSubjectCategory AND
                                                  jsp.Journal_idJournal = j.idJournal AND
                                                  j.idJournal = d.Journal_idJournal)
      WHERE idSubjectCategory IN (SELECT sjp.SubjectCategory_idSubjectCategory
                                  FROM Journal_SubjectCategory_PublishDate sjp
                                  WHERE sjp.Journal_idJournal = old.Journal_idJournal);
  END;

CREATE TRIGGER aggregateData_delete_Document_Affiliation AFTER DELETE ON Document_Affiliation FOR EACH ROW
  BEGIN
    UPDATE Affiliation
      SET affiliation_documentsCount = affiliation_documentsCount - 1
      WHERE idAffiliation = old.Affiliation_idAffiliation;
    UPDATE Document
      SET document_affiliationsCount = document_affiliationsCount - 1
      WHERE idDocument = old.Document_idDocument;
  END;

CREATE TRIGGER aggregateData_delete_Document_Author AFTER DELETE ON Document_Author FOR EACH ROW
  BEGIN
    UPDATE Author
      SET author_documentsCount = author_documentsCount - 1
      WHERE idAuthor = old.Author_idAuthor;
    UPDATE Document
      SET authors = (SELECT group_concat(a.authorName, ", ")
                     FROM Author a, Document_Author da
                     WHERE da.Document_idDocument = Document.idDocument AND                            a.idAuthor = da.Author_idAuthor
                     ORDER BY da.position)
      WHERE idDocument = old.Document_idDocument;
    UPDATE AuthorGroup
      SET authorGroup_documentsCount = (SELECT COUNT(DISTINCT da.Document_idDocument) 
                            FROM AuthorGroup ag, Author a, Document_Author da 
                            WHERE ag.idAuthorGroup = AuthorGroup.idAuthorGroup AND
                                  ag.idAuthorGroup = a.AuthorGroup_idAuthorGroup AND
                                  a.idAuthor = da.Author_idAuthor)
      WHERE idAuthorGroup = (SELECT AuthorGroup_idAuthorGroup FROM Author WHERE idAuthor = old.Author_idAuthor);
  END;

CREATE TRIGGER aggregateData_delete_Document_Reference AFTER DELETE ON Document_Reference FOR EACH ROW
  BEGIN
    UPDATE Reference
      SET reference_documentsCount = reference_documentsCount - 1
      WHERE idReference = old.Reference_idReference;
    UPDATE Document
      SET document_referencesCount = document_referencesCount - 1
      WHERE idDocument = old.Document_idDocument;
    UPDATE ReferenceGroup
      SET referenceGroup_documentsCount = (SELECT COUNT(DISTINCT dr.Document_idDocument) 
                                           FROM ReferenceGroup rg, Reference r, Document_Reference dr 
                                           WHERE rg.idReferenceGroup = ReferenceGroup.idReferenceGroup AND
                                                 rg.idReferenceGroup = r.ReferenceGroup_idReferenceGroup AND
                                                 r.idReference = dr.Reference_idReference)
      WHERE idReferenceGroup = (SELECT ReferenceGroup_idReferenceGroup FROM Reference WHERE idReference = old.Reference_idReference);
    UPDATE ReferenceSource
      SET referenceSource_documentsCount = (SELECT COUNT(DISTINCT dr.Document_idDocument) 
                                            FROM ReferenceSource rs, Reference r, Document_Reference dr 
                                            WHERE rs.idReferenceSource = ReferenceSource.idReferenceSource AND
                                                  rs.idReferenceSource = r.ReferenceSource_idReferenceSource AND
                                                  r.idReference = dr.Reference_idReference)
      WHERE idReferenceSource = (SELECT ReferenceSource_idReferenceSource FROM Reference WHERE idReference = old.Reference_idReference);
    UPDATE ReferenceSourceGroup
      SET referenceSourceGroup_documentsCount = (SELECT COUNT(DISTINCT dr.Document_idDocument) 
                                                 FROM ReferenceSourceGroup rsg, ReferenceSource rs, Reference r, Document_Reference dr
                                                 WHERE rsg.idReferenceSourceGroup = ReferenceSourceGroup.idReferenceSourceGroup AND
                                                       rsg.idReferenceSourceGroup = rs.ReferenceSourceGroup_idReferenceSourceGroup AND
                                                       rs.idReferenceSource = r.ReferenceSource_idReferenceSource AND
                                                       r.idReference = dr.Reference_idReference)
      WHERE idReferenceSourceGroup = (SELECT rs.ReferenceSourceGroup_idReferenceSourceGroup 
                                      FROM ReferenceSource rs, Reference r
                                      WHERE r.idReference = old.Reference_idReference AND                                            rs.idReferenceSource = r.ReferenceSource_idReferenceSource);
    UPDATE AuthorReference
      SET authorReference_documentsCount = (SELECT count(DISTINCT dr.Document_idDocument)
                                            FROM AuthorReference ar, AuthorReference_Reference arr, Reference r, Document_Reference dr
                                            WHERE ar.idAuthorReference = AuthorReference.idAuthorReference AND
                                                 ar.idAuthorReference = arr.AuthorReference_idAuthorReference AND
                                                 arr.Reference_idReference = r.idReference AND
                                                 r.idReference = dr.Reference_idReference)
      WHERE idAuthorReference IN (SELECT arr.AuthorReference_idAuthorReference
                                  FROM AuthorReference_Reference arr, Document_Reference dr, Reference r
                                  WHERE r.idReference = old.Reference_idReference AND
                                       arr.Reference_idReference = r.idReference AND
                                       r.idReference = dr.Reference_idReference);
    UPDATE AuthorReferenceGroup
      SET authorReferenceGroup_documentsCount = (SELECT COUNT(DISTINCT dr.Document_idDocument) 
                                                 FROM AuthorReferenceGroup arg, AuthorReference ar, AuthorReference_Reference arr, Reference r, Document_Reference dr 
                                                 WHERE arg.idAuthorReferenceGroup = AuthorReferenceGroup.idAuthorReferenceGroup AND
                                                      arg.idAuthorReferenceGroup = ar.AuthorReferenceGroup_idAuthorReferenceGroup AND
                                                      ar.idAuthorReference = arr.AuthorReference_idAuthorReference AND
                                                      arr.Reference_idReference = r.idReference AND
                                                      r.idReference = dr.Reference_idReference)
      WHERE idAuthorReferenceGroup IN (SELECT DISTINCT ar.AuthorReferenceGroup_idAuthorReferenceGroup
                                       FROM AuthorReference ar, AuthorReference_Reference arr, Reference r, Document_Reference dr
                                       WHERE r.idReference = old.Reference_idReference AND
                                            ar.idAuthorReference = arr.AuthorReference_idAuthorReference AND
                                            arr.Reference_idReference = r.idReference AND
                                            r.idReference = dr.Reference_idReference);
  END;

CREATE TRIGGER aggregateData_delete_Document_Word AFTER DELETE ON Document_Word FOR EACH ROW
  BEGIN
    UPDATE Word 
      SET word_documentsCount = word_documentsCount - 1,
          roleAuthorCount = CASE old.isAuthorWord WHEN 1 THEN roleAuthorCount - 1 ELSE roleAuthorCount END,
          roleSourceCount = CASE old.isSourceWord WHEN 1 THEN roleSourceCount - 1 ELSE roleSourceCount END,
          roleAddedCount = CASE old.isAddedWord WHEN 1 THEN roleAddedCount - 1 ELSE roleAddedCount END
      WHERE idWord = old.Word_idWord;
    UPDATE Document 
      SET document_wordsCount = document_wordsCount - 1,
          authorWordsCount = CASE old.isAuthorWord WHEN 1 THEN authorWordsCount - 1 ELSE authorWordsCount END,
          sourceWordsCount = CASE old.isSourceWord WHEN 1 THEN sourceWordsCount - 1 ELSE sourceWordsCount END,
          addedWordsCount = CASE old.isAddedWord WHEN 1 THEN addedWordsCount - 1 ELSE addedWordsCount END 
      WHERE idDocument = old.Document_idDocument;
    UPDATE WordGroup 
      SET wordGroup_documentsCount = (SELECT COUNT(DISTINCT dw.Document_idDocument) 
                                      FROM WordGroup wg, Word w, Document_Word dw
                                      WHERE wg.idWordGroup = WordGroup.idWordGroup AND
                                            wg.idWordGroup = w.WordGroup_idWordGroup AND
                                            w.idWord = dw.Word_idWord)
      WHERE idWordGroup = (SELECT WordGroup_idWordGroup 
                           FROM Word 
                           WHERE idWord = old.Word_idWord);
  END;

CREATE TRIGGER aggregateData_delete_Journal_SubjectCategory_PublishDate AFTER DELETE ON Journal_SubjectCategory_PublishDate FOR EACH ROW
  BEGIN
    UPDATE SubjectCategory
      SET subjectCategory_journalsCount = (SELECT count(DISTINCT j.idJournal)
                                            FROM SubjectCategory sc, Journal_SubjectCategory_PublishDate jsp, Journal j
                                            WHERE sc.idSubjectCategory = SubjectCategory.idSubjectCategory AND
                                                  sc.idSubjectCategory = jsp.SubjectCategory_idSubjectCategory AND
                                                  jsp.Journal_idJournal = j.idJournal),
          subjectCategory_documentsCount = subjectCategory_documentsCount - (SELECT count(d.idDocument)
                                                                             FROM Journal j, Document d
                                                                             WHERE j.idJournal = old.Journal_idJournal AND
                                                                                   j.idJournal = d.Journal_idJournal)
      WHERE idSubjectCategory = old.SubjectCategory_idSubjectCategory;
  END;

CREATE TRIGGER aggregateData_delete_PublishDate_Period AFTER DELETE ON PublishDate_Period FOR EACH ROW
  BEGIN
    UPDATE Period
      SET period_publishDatesCount = period_publishDatesCount - 1,
          period_documentsCount = (SELECT COUNT(d.idDocument)
                                   FROM Period p, PublishDate_Period pup, PublishDate pu, Document d
                                   WHERE p.idPeriod = Period.idPeriod AND
                                         p.idPeriod = pup.Period_idPeriod AND
                                         pup.PublishDate_idPublishDate = pu.idPublishDate AND
                                         pu.idPublishDate = d.PublishDate_idPublishDate)
      WHERE idPeriod = old.Period_idPeriod;
  END;

CREATE TRIGGER aggregateData_delete_Reference AFTER DELETE ON Reference FOR EACH ROW
  BEGIN
    UPDATE ReferenceGroup
      SET itemsCount = itemsCount - 1,
          referenceGroup_documentsCount = (SELECT COUNT (DISTINCT dr.Document_idDocument)
                                           FROM ReferenceGroup rg, Reference r, Document_Reference dr
                                           WHERE rg.idReferenceGroup = ReferenceGroup.idReferenceGroup AND
                                                 rg.idReferenceGroup = r.ReferenceGroup_idReferenceGroup AND
                                                 r.idReference = dr.Reference_idReference)
      WHERE idReferenceGroup = old.ReferenceGroup_idReferenceGroup;
    UPDATE ReferenceSource
      SET referenceSource_referencesCount = referenceSource_referencesCount - 1,
          referenceSource_documentsCount = (SELECT COUNT(DISTINCT dr.Document_idDocument)
                                            FROM ReferenceSource rs, Reference r, Document_Reference dr
                                            WHERE idReferenceSource = ReferenceSource.idReferenceSource AND
                                                  rs.idReferenceSource = r.ReferenceSource_idReferenceSource AND
                                                  r.idReference = dr.Reference_idReference)
      WHERE idReferenceSource = old.ReferenceSource_idReferenceSource;
  END;

CREATE TRIGGER aggregateData_delete_ReferenceSource AFTER DELETE ON ReferenceSource FOR EACH ROW
  BEGIN
    UPDATE ReferenceSourceGroup
      SET itemsCount = itemsCount - 1,
          referenceSourceGroup_documentsCount = (SELECT COUNT (DISTINCT dr.Document_idDocument)
                                                 FROM ReferenceSourceGroup rsg, ReferenceSource rs, Reference r, Document_Reference dr
                                                 WHERE rsg.idReferenceSourceGroup = ReferenceSourceGroup.idReferenceSourceGroup AND
                                                       rsg.idReferenceSourceGroup = rs.ReferenceSourceGroup_idReferenceSourceGroup AND
                                                       rs.idReferenceSource = r.ReferenceSource_idReferenceSource AND
                                                       r.idReference = dr.Reference_idReference)
      WHERE idReferenceSourceGroup = old.ReferenceSourceGroup_idReferenceSourceGroup;
  END;

CREATE TRIGGER aggregateData_delete_Word AFTER DELETE ON Word FOR EACH ROW
  BEGIN
    UPDATE WordGroup
      SET itemsCount = itemsCount - 1,
          wordGroup_documentsCount = (SELECT COUNT (DISTINCT dw.Document_idDocument)
                                      FROM WordGroup wg, Word w, Document_Word dw
                                      WHERE wg.idWordGroup = WordGroup.idWordGroup AND
                                            wg.idWordGroup = w.WordGroup_idWordGroup AND
                                            w.idWord = dw.Word_idWord)
      WHERE idWordGroup = old.WordGroup_idWordGroup;
  END;

CREATE TRIGGER aggregateData_insert_AuthorReference_Reference AFTER INSERT ON AuthorReference_Reference FOR EACH ROW
  BEGIN
    UPDATE AuthorReference
      SET authorReference_referencesCount = authorReference_referencesCount + 1,
          authorReference_documentsCount = (SELECT count(DISTINCT dr.Document_idDocument)
                                            FROM AuthorReference ar, AuthorReference_Reference arr, Reference r, Document_Reference dr
                                            WHERE ar.idAuthorReference = AuthorReference.idAuthorReference AND
                                                  ar.idAuthorReference = arr.AuthorReference_idAuthorReference AND
                                                  arr.Reference_idReference = r.idReference AND
                                                  r.idReference = dr.Reference_idReference)
      WHERE idAuthorReference = new.AuthorReference_idAuthorReference;
    UPDATE AuthorReferenceGroup
      SET authorReferenceGroup_documentsCount = (SELECT COUNT(DISTINCT dr.Document_idDocument) 
                                                 FROM AuthorReferenceGroup arg, AuthorReference ar, AuthorReference_Reference arr, Reference r, Document_Reference dr 
                                                 WHERE arg.idAuthorReferenceGroup =  AuthorReferenceGroup.idAuthorReferenceGroup AND
                                                       arg.idAuthorReferenceGroup = ar.AuthorReferenceGroup_idAuthorReferenceGroup AND
                                                       ar.idAuthorReference = arr.AuthorReference_idAuthorReference AND
                                                       arr.Reference_idReference = r.idReference AND
                                                       r.idReference = dr.Reference_idReference)
      WHERE idAuthorReferenceGroup = (SELECT AuthorReferenceGroup_idAuthorReferenceGroup FROM AuthorReference WHERE idAuthorReference = new.AuthorReference_idAuthorReference);
  END;

CREATE TRIGGER aggregateData_insert_Author_Affiliation AFTER INSERT ON Author_Affiliation FOR EACH ROW
  BEGIN
    UPDATE Affiliation
      SET affiliation_authorsCount = affiliation_authorsCount + 1
      WHERE idAffiliation = new.Affiliation_idAffiliation;
    UPDATE Author
      SET author_affiliationsCount = author_affiliationsCount + 1
      WHERE idAuthor = new.Author_idAuthor;
  END;

CREATE TRIGGER aggregateData_insert_Document_Affiliation AFTER INSERT ON Document_Affiliation FOR EACH ROW
  BEGIN
    UPDATE Affiliation
      SET affiliation_documentsCount = affiliation_documentsCount + 1
      WHERE idAffiliation = new.Affiliation_idAffiliation;
    UPDATE Document
      SET document_affiliationsCount = document_affiliationsCount + 1
      WHERE idDocument = new.Document_idDocument;
  END;

CREATE TRIGGER aggregateData_insert_Document_Author AFTER INSERT ON Document_Author FOR EACH ROW
  BEGIN
    UPDATE Author
      SET author_documentsCount = author_documentsCount + 1
      WHERE idAuthor = new.Author_idAuthor;
    UPDATE Document
      SET authors = (SELECT group_concat(authorName, ", ")
                     FROM Author a, Document_Author da
                     WHERE da.Document_idDocument = Document.idDocument AND                            a.idAuthor = da.Author_idAuthor
                     ORDER BY da.position)
      WHERE idDocument = new.Document_idDocument;
    UPDATE AuthorGroup
      SET authorGroup_documentsCount = (SELECT COUNT(DISTINCT da.Document_idDocument) 
                            FROM AuthorGroup ag, Author a, Document_Author da 
                            WHERE ag.idAuthorGroup = AuthorGroup.idAuthorGroup AND
                                  ag.idAuthorGroup = a.AuthorGroup_idAuthorGroup AND
                                  a.idAuthor = da.Author_idAuthor)
      WHERE idAuthorGroup = (SELECT AuthorGroup_idAuthorGroup FROM Author WHERE idAuthor = new.Author_idAuthor);
  END;

CREATE TRIGGER aggregateData_insert_Document_Reference AFTER INSERT ON Document_Reference FOR EACH ROW
  BEGIN
    UPDATE Reference
      SET reference_documentsCount = reference_documentsCount + 1
      WHERE idReference = new.Reference_idReference;
    UPDATE Document
      SET document_referencesCount = document_referencesCount + 1
      WHERE idDocument = new.Document_idDocument;
    UPDATE ReferenceGroup
      SET referenceGroup_documentsCount = (SELECT COUNT(DISTINCT dr.Document_idDocument) 
                                           FROM ReferenceGroup rg, Reference r, Document_Reference dr 
                                           WHERE rg.idReferenceGroup = ReferenceGroup.idReferenceGroup AND
                                                 rg.idReferenceGroup = r.ReferenceGroup_idReferenceGroup AND
                                                 r.idReference = dr.Reference_idReference)
      WHERE idReferenceGroup = (SELECT ReferenceGroup_idReferenceGroup FROM Reference WHERE idReference = new.Reference_idReference);
    UPDATE ReferenceSource
      SET referenceSource_documentsCount = (SELECT COUNT(DISTINCT dr.Document_idDocument) 
                                            FROM ReferenceSource rs, Reference r, Document_Reference dr 
                                            WHERE rs.idReferenceSource = ReferenceSource.idReferenceSource AND
                                                  rs.idReferenceSource = r.ReferenceSource_idReferenceSource AND
                                                  r.idReference = dr.Reference_idReference)
      WHERE idReferenceSource = (SELECT ReferenceSource_idReferenceSource FROM Reference WHERE idReference = new.Reference_idReference);
    UPDATE ReferenceSourceGroup
      SET referenceSourceGroup_documentsCount = (SELECT COUNT(DISTINCT dr.Document_idDocument) 
                                                 FROM ReferenceSourceGroup rsg, ReferenceSource rs, Reference r, Document_Reference dr
                                                 WHERE rsg.idReferenceSourceGroup = ReferenceSourceGroup.idReferenceSourceGroup AND
                                                       rsg.idReferenceSourceGroup = rs.ReferenceSourceGroup_idReferenceSourceGroup AND
                                                       rs.idReferenceSource = r.ReferenceSource_idReferenceSource AND
                                                       r.idReference = dr.Reference_idReference)
      WHERE idReferenceSourceGroup = (SELECT rs.ReferenceSourceGroup_idReferenceSourceGroup 
                                      FROM ReferenceSource rs, Reference r
                                      WHERE r.idReference = new.Reference_idReference AND                                            rs.idReferenceSource = r.ReferenceSource_idReferenceSource);
    UPDATE AuthorReference
      SET authorReference_documentsCount = (SELECT count(DISTINCT dr.Document_idDocument)
                                            FROM AuthorReference ar, AuthorReference_Reference arr, Reference r, Document_Reference dr
                                            WHERE ar.idAuthorReference = AuthorReference.idAuthorReference AND
                                                 ar.idAuthorReference = arr.AuthorReference_idAuthorReference AND
                                                 arr.Reference_idReference = r.idReference AND
                                                 r.idReference = dr.Reference_idReference)
      WHERE idAuthorReference IN (SELECT arr.AuthorReference_idAuthorReference
                                  FROM AuthorReference_Reference arr, Document_Reference dr, Reference r
                                  WHERE r.idReference = new.Reference_idReference AND
                                       arr.Reference_idReference = r.idReference AND
                                       r.idReference = dr.Reference_idReference);
    UPDATE AuthorReferenceGroup
      SET authorReferenceGroup_documentsCount = (SELECT COUNT(DISTINCT dr.Document_idDocument) 
                                                 FROM AuthorReferenceGroup arg, AuthorReference ar, AuthorReference_Reference arr, Reference r, Document_Reference dr 
                                                 WHERE arg.idAuthorReferenceGroup = AuthorReferenceGroup.idAuthorReferenceGroup AND
                                                      arg.idAuthorReferenceGroup = ar.AuthorReferenceGroup_idAuthorReferenceGroup AND
                                                      ar.idAuthorReference = arr.AuthorReference_idAuthorReference AND
                                                      arr.Reference_idReference = r.idReference AND
                                                      r.idReference = dr.Reference_idReference)
      WHERE idAuthorReferenceGroup IN (SELECT DISTINCT ar.AuthorReferenceGroup_idAuthorReferenceGroup
                                       FROM AuthorReference ar, AuthorReference_Reference arr, Reference r, Document_Reference dr
                                       WHERE r.idReference = new.Reference_idReference AND
                                            ar.idAuthorReference = arr.AuthorReference_idAuthorReference AND
                                            arr.Reference_idReference = r.idReference AND
                                            r.idReference = dr.Reference_idReference);
  END;

CREATE TRIGGER aggregateData_insert_Document_Word AFTER INSERT ON Document_Word FOR EACH ROW
  BEGIN
    UPDATE Word 
      SET word_documentsCount = word_documentsCount + 1,
          roleAuthorCount = CASE new.isAuthorWord WHEN 1 THEN roleAuthorCount + 1 ELSE roleAuthorCount END,
          roleSourceCount = CASE new.isSourceWord WHEN 1 THEN roleSourceCount + 1 ELSE roleSourceCount END,
          roleAddedCount = CASE new.isAddedWord WHEN 1 THEN roleAddedCount + 1 ELSE roleAddedCount END
      WHERE idWord = new.Word_idWord;
    UPDATE Document 
      SET document_wordsCount = document_wordsCount + 1,
          authorWordsCount = CASE new.isAuthorWord WHEN 1 THEN authorWordsCount + 1 ELSE authorWordsCount END,
          sourceWordsCount = CASE new.isSourceWord WHEN 1 THEN sourceWordsCount + 1 ELSE sourceWordsCount END,
          addedWordsCount = CASE new.isAddedWord WHEN 1 THEN addedWordsCount + 1 ELSE addedWordsCount END 
      WHERE idDocument = new.Document_idDocument;
    UPDATE WordGroup 
      SET wordGroup_documentsCount = (SELECT COUNT(DISTINCT dw.Document_idDocument) 
                                      FROM WordGroup wg, Word w, Document_Word dw
                                      WHERE wg.idWordGroup = WordGroup.idWordGroup AND
                                            wg.idWordGroup = w.WordGroup_idWordGroup AND
                                            w.idWord = dw.Word_idWord)
      WHERE idWordGroup = (SELECT WordGroup_idWordGroup 
                           FROM Word 
                           WHERE idWord = new.Word_idWord);
  END;

CREATE TRIGGER aggregateData_insert_Journal_SubjectCategory_PublishDate AFTER INSERT ON Journal_SubjectCategory_PublishDate FOR EACH ROW
  BEGIN
    UPDATE SubjectCategory
      SET subjectCategory_journalsCount = (SELECT count(DISTINCT j.idJournal)
                                            FROM SubjectCategory sc, Journal_SubjectCategory_PublishDate jsp, Journal j
                                            WHERE sc.idSubjectCategory = SubjectCategory.idSubjectCategory AND
                                                  sc.idSubjectCategory = jsp.SubjectCategory_idSubjectCategory AND
                                                  jsp.Journal_idJournal = j.idJournal),
          subjectCategory_documentsCount = subjectCategory_documentsCount + (SELECT count(d.idDocument)
                                                                             FROM Journal j, Document d
                                                                             WHERE j.idJournal = new.Journal_idJournal AND
                                                                                   j.idJournal = d.Journal_idJournal)
      WHERE idSubjectCategory = new.SubjectCategory_idSubjectCategory;
  END;

CREATE TRIGGER aggregateData_insert_PublishDate_Period AFTER INSERT ON PublishDate_Period FOR EACH ROW
  BEGIN
    UPDATE Period
      SET period_publishDatesCount = period_publishDatesCount + 1,
          period_documentsCount = (SELECT COUNT(d.idDocument)
                                   FROM Period p, PublishDate_Period pup, PublishDate pu, Document d
                                   WHERE p.idPeriod = Period.idPeriod AND
                                         p.idPeriod = pup.Period_idPeriod AND
                                         pup.PublishDate_idPublishDate = pu.idPublishDate AND
                                         pu.idPublishDate = d.PublishDate_idPublishDate)
      WHERE idPeriod = new.Period_idPeriod;
  END;

CREATE TRIGGER aggregateData_update_AuthorReference_AuthorReferenceGroup_idAuthorReferenceGroup AFTER UPDATE OF AuthorReferenceGroup_idAuthorReferenceGroup ON AuthorReference FOR EACH ROW
  WHEN new.AuthorReferenceGroup_idAuthorReferenceGroup IS NOT old.AuthorReferenceGroup_idAuthorReferenceGroup
  BEGIN
    UPDATE AuthorReferenceGroup
      SET itemsCount = itemsCount - 1
      WHERE idAuthorReferenceGroup IN (old.AuthorReferenceGroup_idAuthorReferenceGroup);
    UPDATE AuthorReferenceGroup
      SET itemsCount = itemsCount + 1
      WHERE idAuthorReferenceGroup IN (new.AuthorReferenceGroup_idAuthorReferenceGroup);
    UPDATE AuthorReferenceGroup
      SET authorReferenceGroup_documentsCount = (SELECT COUNT(DISTINCT dr.Document_idDocument) 
                                                 FROM AuthorReferenceGroup arg, AuthorReference ar, AuthorReference_Reference arr, Reference r, Document_Reference dr 
                                                 WHERE arg.idAuthorReferenceGroup = AuthorReferenceGroup.idAuthorReferenceGroup AND
                                                       arg.idAuthorReferenceGroup = ar.AuthorReferenceGroup_idAuthorReferenceGroup AND
                                                       ar.idAuthorReference = arr.AuthorReference_idAuthorReference AND
                                                       arr.Reference_idReference = r.idReference AND
                                                       r.idReference = dr.Reference_idReference)
      WHERE idAuthorReferenceGroup IN (new.AuthorReferenceGroup_idAuthorReferenceGroup, old.AuthorReferenceGroup_idAuthorReferenceGroup);
  END;

CREATE TRIGGER aggregateData_update_Author_AuthorGroup_idAuthorGroup AFTER UPDATE OF AuthorGroup_idAuthorGroup ON Author FOR EACH ROW
  WHEN new.AuthorGroup_idAuthorGroup IS NOT old.AuthorGroup_idAuthorGroup
  BEGIN
    UPDATE AuthorGroup
      SET itemsCount = itemsCount - 1
      WHERE idAuthorGroup IN (old.AuthorGroup_idAuthorGroup);
    UPDATE AuthorGroup
      SET itemsCount = itemsCount + 1
      WHERE idAuthorGroup IN (new.AuthorGroup_idAuthorGroup);
    UPDATE AuthorGroup
      SET authorGroup_documentsCount = (SELECT COUNT(DISTINCT da.Document_idDocument) 
                                        FROM AuthorGroup ag, Author a, Document_Author da 
                                        WHERE ag.idAuthorGroup = AuthorGroup.idAuthorGroup AND
                                              ag.idAuthorGroup = a.AuthorGroup_idAuthorGroup AND
                                              a.idAuthor = da.Author_idAuthor)
      WHERE idAuthorGroup IN (new.AuthorGroup_idAuthorGroup, old.AuthorGroup_idAuthorGroup);
  END;

CREATE TRIGGER aggregateData_update_Document_Author_position AFTER UPDATE OF position ON Document_Author FOR EACH ROW
  WHEN new.position != old.position
  BEGIN
    UPDATE Document
      SET authors = (SELECT group_concat(authorName, ", ")
                     FROM Author a, Document_Author da
                     WHERE da.Document_idDocument = Document.idDocument AND                            a.idAuthor = da.Author_idAuthor
                     ORDER BY da.position)
      WHERE idDocument = old.Document_idDocument;
  END;

CREATE TRIGGER aggregateData_update_Document_Journal_idJournal AFTER UPDATE OF Journal_idJournal ON Document FOR EACH ROW
  BEGIN
    UPDATE Journal
      SET journal_documentsCount = journal_documentsCount - 1
      WHERE idJournal IN (old.Journal_idJournal);
    UPDATE Journal
      SET journal_documentsCount = journal_documentsCount + 1
      WHERE idJournal IN (new.Journal_idJournal);
    UPDATE SubjectCategory
          SET subjectCategory_documentsCount = subjectCategory_documentsCount + 1
      WHERE idSubjectCategory IN (SELECT DISTINCT sjp.SubjectCategory_idSubjectCategory
                                  FROM Journal_SubjectCategory_PublishDate sjp
                                  WHERE sjp.Journal_idJournal IN (new.Journal_idJournal));
    UPDATE SubjectCategory
          SET subjectCategory_documentsCount = subjectCategory_documentsCount - 1
      WHERE idSubjectCategory IN (SELECT DISTINCT sjp.SubjectCategory_idSubjectCategory
                                  FROM Journal_SubjectCategory_PublishDate sjp
                                  WHERE sjp.Journal_idJournal IN (old.Journal_idJournal));
  END;

CREATE TRIGGER aggregateData_update_Document_PublishDate_idPublishDate AFTER UPDATE OF PublishDate_idPublishDate ON Document FOR EACH ROW
  BEGIN
    UPDATE Document
      SET year = (SELECT year FROM PublishDate WHERE idPublishDate = new.PublishDate_idPublishDate)
      WHERE idDocument = new.idDocument;
    UPDATE PublishDate
      SET publishDate_documentsCount = (SELECT count(d.idDocument)
                                        FROM Document d
                                        WHERE d.PublishDate_idPublishDate = PublishDate.idPublishDate)
      WHERE idPublishDate IN (new.PublishDate_idPublishDate, old.PublishDate_idPublishDate);
    UPDATE Period
      SET period_documentsCount = (SELECT count(d.idDocument)
                                   FROM Period p, PublishDate_Period pup, PublishDate pu, Document d
                                   WHERE p.idPeriod = Period.idPeriod AND
                                         p.idPeriod = pup.Period_idPeriod AND
                                         pup.PublishDate_idPublishDate = pu.idPublishDate AND
                                         pu.idPublishDate = d.PublishDate_idPublishDate)
      WHERE idPeriod IN (SELECT p.idPeriod
                         FROM Period p, PublishDate_Period pup
                         WHERE pup.PublishDate_idPublishDate IN (new.PublishDate_idPublishDate, old.PublishDate_idPublishDate) AND                               p.idPeriod = pup.Period_idPeriod);
  END;

CREATE TRIGGER aggregateData_update_Document_Word_isAddedWord AFTER UPDATE OF isAddedWord ON Document_Word FOR EACH ROW
  WHEN new.isAddedWord != old.isAddedWord
  BEGIN
    UPDATE Word
      SET roleAddedCount = CASE new.isAddedWord WHEN 1 THEN roleAddedCount + 1 ELSE roleAddedCount - 1 END
      WHERE idWord = old.Word_idWord;
    UPDATE Document
      SET addedWordsCount = CASE new.isAddedWord WHEN 1 THEN addedWordsCount + 1 ELSE addedWordsCount - 1 END
      WHERE idDocument = old.Document_idDocument;
  END;

CREATE TRIGGER aggregateData_update_Document_Word_isAuthorWord AFTER UPDATE OF isAuthorWord ON Document_Word FOR EACH ROW
  WHEN new.isAuthorWord != old.isAuthorWord
  BEGIN
    UPDATE Word
      SET roleAuthorCount = CASE new.isAuthorWord WHEN 1 THEN roleAuthorCount + 1 ELSE roleAuthorCount - 1 END
      WHERE idWord = old.Word_idWord;
    UPDATE Document
      SET authorWordsCount = CASE new.isAuthorWord WHEN 1 THEN authorWordsCount + 1 ELSE authorWordsCount - 1 END
      WHERE idDocument = old.Document_idDocument;
  END;

CREATE TRIGGER aggregateData_update_Document_Word_isSourceWord AFTER UPDATE OF isSourceWord ON Document_Word FOR EACH ROW
  WHEN new.isSourceWord != old.isSourceWord
  BEGIN
    UPDATE Word
      SET roleSourceCount = CASE new.isSourceWord WHEN 1 THEN roleSourceCount + 1 ELSE roleSourceCount - 1 END
      WHERE idWord = old.Word_idWord;
    UPDATE Document
      SET sourceWordsCount = CASE new.isSourceWord WHEN 1 THEN sourceWordsCount + 1 ELSE sourceWordsCount - 1 END
      WHERE idDocument = old.Document_idDocument;
  END;

CREATE TRIGGER aggregateData_update_ReferenceSource_ReferenceSourceGroup_idReferenceSourceGroup AFTER UPDATE OF ReferenceSourceGroup_idReferenceSourceGroup ON ReferenceSource FOR EACH ROW
  WHEN new.ReferenceSourceGroup_idReferenceSourceGroup IS NOT old.ReferenceSourceGroup_idReferenceSourceGroup
  BEGIN
    UPDATE ReferenceSourceGroup
      SET itemsCount = itemsCount - 1
      WHERE idReferenceSourceGroup IN (old.ReferenceSourceGroup_idReferenceSourceGroup);
    UPDATE ReferenceSourceGroup
      SET itemsCount = itemsCount + 1
      WHERE idReferenceSourceGroup IN (new.ReferenceSourceGroup_idReferenceSourceGroup);
    UPDATE ReferenceSourceGroup
      SET referenceSourceGroup_documentsCount = (SELECT COUNT(DISTINCT dr.Document_idDocument) 
                                                 FROM ReferenceSourceGroup rsg, ReferenceSource rs, Reference r, Document_Reference dr
                                                 WHERE rsg.idReferenceSourceGroup = ReferenceSourceGroup.idReferenceSourceGroup AND
                                                       rsg.idReferenceSourceGroup = rs.ReferenceSourceGroup_idReferenceSourceGroup AND
                                                       rs.idReferenceSource = r.ReferenceSource_idReferenceSource AND
                                                       r.idReference = dr.Reference_idReference)
      WHERE idReferenceSourceGroup IN (ReferenceSourceGroup.idReferenceSourceGroup);
  END;

CREATE TRIGGER aggregateData_update_ReferenceSource_idReferenceSource AFTER UPDATE OF ReferenceSource_idReferenceSource ON Reference FOR EACH ROW
  WHEN new.ReferenceSource_idReferenceSource IS NOT old.ReferenceSource_idReferenceSource
  BEGIN
    UPDATE ReferenceSource
      SET referenceSource_referencesCount = referenceSource_referencesCount - 1
      WHERE idReferenceSource IN (old.ReferenceSource_idReferenceSource);
    UPDATE ReferenceSource
      SET referenceSource_referencesCount = referenceSource_referencesCount + 1
      WHERE idReferenceSource IN (new.ReferenceSource_idReferenceSource);
    UPDATE ReferenceSource
      SET referenceSource_documentsCount = (SELECT COUNT(DISTINCT dr.Document_idDocument)
                            FROM ReferenceSource rs, Reference r, Document_Reference dr
                             WHERE idReferenceSource = ReferenceSource.idReferenceSource AND
                                   rs.idReferenceSource = r.ReferenceSource_idReferenceSource AND
                                   r.idReference = dr.Reference_idReference)
      WHERE idReferenceSource IN (new.ReferenceSource_idReferenceSource, old.ReferenceSource_idReferenceSource);
    UPDATE ReferenceSourceGroup
      SET referenceSourceGroup_documentsCount = (SELECT COUNT(DISTINCT dr.Document_idDocument) 
                            FROM ReferenceSourceGroup rsg, ReferenceSource rs, Reference r, Document_Reference dr 
                            WHERE rsg.idReferenceSourceGroup = ReferenceSourceGroup.idReferenceSourceGroup AND
                                 rsg.idReferenceSourceGroup = rs.ReferenceSourceGroup_idReferenceSourceGroup AND
                                 rs.idReferenceSource = r.ReferenceSource_idReferenceSource AND
                                 r.idReference = dr.Reference_idReference)
      WHERE idReferenceSourceGroup = (SELECT rs.ReferenceSourceGroup_idReferenceSourceGroup 
                                      FROM Reference r, ReferenceSource rs
                                      WHERE r.idReference = new.idReference AND r.ReferenceSource_idReferenceSource = rs.idReferenceSource);
  END;

CREATE TRIGGER aggregateData_update_Reference_ReferenceGroup_idReferenceGroup AFTER UPDATE OF ReferenceGroup_idReferenceGroup ON Reference FOR EACH ROW
  WHEN new.ReferenceGroup_idReferenceGroup IS NOT old.ReferenceGroup_idReferenceGroup
  BEGIN
    UPDATE ReferenceGroup
      SET itemsCount = itemsCount - 1
      WHERE idReferenceGroup IN (old.ReferenceGroup_idReferenceGroup);
    UPDATE ReferenceGroup
      SET itemsCount = itemsCount + 1
      WHERE idReferenceGroup IN (new.ReferenceGroup_idReferenceGroup);
    UPDATE ReferenceGroup
      SET referenceGroup_documentsCount = (SELECT COUNT(DISTINCT dr.Document_idDocument) 
                                           FROM ReferenceGroup rg, Reference r, Document_Reference dr
                                           WHERE rg.idReferenceGroup = ReferenceGroup.idReferenceGroup AND
                                                 rg.idReferenceGroup = r.ReferenceGroup_idReferenceGroup AND
                                                 r.idReference = dr.Reference_idReference)
      WHERE idReferenceGroup IN (new.ReferenceGroup_idReferenceGroup, old.ReferenceGroup_idReferenceGroup);
  END;

CREATE TRIGGER aggregateData_update_Word_WordGroup_idWordGroup AFTER UPDATE OF WordGroup_idWordGroup ON Word FOR EACH ROW
  WHEN new.WordGroup_idWordGroup IS NOT old.WordGroup_idWordGroup
  BEGIN
    UPDATE WordGroup
      SET itemsCount = itemsCount - 1
      WHERE idWordGroup IN (old.WordGroup_idWordGroup);
    UPDATE WordGroup
      SET itemsCount = itemsCount + 1
      WHERE idWordGroup IN (new.WordGroup_idWordGroup);
    UPDATE WordGroup
      SET wordGroup_documentsCount = (SELECT COUNT(DISTINCT dw.Document_idDocument) 
                                      FROM WordGroup wg, Word w, Document_Word dw 
                                      WHERE wg.idWordGroup = WordGroup.idWordGroup AND
                                            wg.idWordGroup = w.WordGroup_idWordGroup AND
                                            w.idWord = dw.Word_idWord)
      WHERE idWordGroup IN (new.WordGroup_idWordGroup, old.WordGroup_idWordGroup);
  END;

CREATE TABLE CountryGroup(
  idCountryGroup INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL CHECK(idCountryGroup>=0),
  groupName VARCHAR NOT NULL UNIQUE,
  stopGroup BOOLEAN DEFAULT FALSE,
  itemsCount INTEGER CHECK(itemsCount>=0) DEFAULT 0,
  countryGroup_documentsCount INTEGER CHECK(countryGroup_documentsCount>=0) DEFAULT 0
);

CREATE TABLE Country(
  idCountry INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL CHECK(idCountry>=0),
  countryName VARCHAR NOT NULL UNIQUE,
  CountryGroup_idCountryGroup INTEGER CHECK(CountryGroup_idCountryGroup>=0),
  country_documentsCount INTEGER CHECK(country_documentsCount>=0) DEFAULT 0,
  CONSTRAINT fk_Country_CountryGroup
     FOREIGN KEY(CountryGroup_idCountryGroup)
     REFERENCES CountryGroup(idCountryGroup)
     ON DELETE SET NULL
     ON UPDATE CASCADE
);

CREATE TABLE Document_Country(
  Country_idCountry INTEGER NOT NULL CHECK(Country_idCountry>=0),
  Document_idDocument INTEGER NOT NULL CHECK(Document_idDocument>=0),
  PRIMARY KEY(Country_idCountry,Document_idDocument),
  CONSTRAINT fk_DocumentCountry_Country
     FOREIGN KEY(Country_idCountry)
     REFERENCES Country(idCountry)
     ON DELETE CASCADE
     ON UPDATE CASCADE,
  CONSTRAINT fk_DocumentCountry_Document
     FOREIGN KEY(Document_idDocument)
     REFERENCES Document(idDocument)
     ON DELETE CASCADE
     ON UPDATE CASCADE
);

CREATE UNIQUE INDEX fk_Country_CountryGroup ON Country(CountryGroup_idCountryGroup);

CREATE UNIQUE INDEX fk_DocumentCountry ON Document_Country(Country_idCountry,Document_idDocument);

CREATE INDEX fk_DocumentCountry_Country ON Document_Country(Country_idCountry);

CREATE INDEX fk_DocumentCountry_Document ON Document_Country(Document_idDocument);

CREATE TABLE DocumentMetadata(
  Document_idDocument INTEGER NOT NULL CHECK(Document_idDocument>=0),
  metaKey VARCHAR NOT NULL,
  metaValue VARCHAR,
  PRIMARY KEY(Document_idDocument,metaKey),
  CONSTRAINT fk_DocumentMetadata_Document
     FOREIGN KEY(Document_idDocument)
     REFERENCES Document(idDocument)
     ON DELETE CASCADE
     ON UPDATE CASCADE
);

CREATE INDEX fk_DocumentMetadata_Document ON DocumentMetadata(Document_idDocument);

CREATE TABLE ReferenceRaw(
  Reference_idReference INTEGER PRIMARY KEY NOT NULL CHECK(Reference_idReference>=0),
  rawReference VARCHAR NOT NULL,
  CONSTRAINT fk_ReferenceRaw_Reference
     FOREIGN KEY(Reference_idReference)
     REFERENCES Reference(idReference)
     ON DELETE CASCADE
     ON UPDATE CASCADE
);
"""


def cria(conexao: sqlite3.Connection) -> None:
    """Cria todas as tabelas, índices e gatilhos no banco aberto."""
    anterior = conexao.isolation_level
    conexao.isolation_level = None
    try:
        conexao.execute("PRAGMA foreign_keys = OFF;")
        conexao.executescript(INSTRUCOES)
        conexao.execute("PRAGMA foreign_keys = ON;")
    finally:
        conexao.isolation_level = anterior


def marca_versao(conexao: sqlite3.Connection) -> None:
    conexao.execute(
        "INSERT OR REPLACE INTO KnowledgeBaseVersion(knowledgeBaseVersion) "
        "VALUES (?);", (VERSAO,))
