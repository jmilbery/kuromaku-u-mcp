CREATE TABLE "ku"."class_year" (
"class_year" int4 NOT NULL,
"class_short_name" char(2) NOT NULL,
"class_name" varchar(24) NOT NULL,
"is_alumni" bool,
"sort_order" int8,
"create_date" timestamp(0),
"last_update_date" timestamp(0),
"updated_by_user_id" int8 DEFAULT 0,
CONSTRAINT "ku_class_years_pkey" PRIMARY KEY ("class_year") 
)
WITHOUT OIDS;
COMMENT ON TABLE "ku"."class_year" IS 'Table of class years — one row for Freshmen, Sophomores, Juniors and Seniors — and one row for every “alumni” year.';
COMMENT ON COLUMN "ku"."class_year"."class_year" IS 'Primary key, integer value that denotes the class year, 2019, 2020, 2021, etc.   The value is the graduation year, so 2019 would indicate the 2018-2019 academic year.';
COMMENT ON COLUMN "ku"."class_year"."class_short_name" IS 'Two letter value for the class, FR, SO, JR, SR, AL';
COMMENT ON COLUMN "ku"."class_year"."class_name" IS 'Full name of the class, Freshman, Sophomore, Junior, Senior, Alumni';
COMMENT ON COLUMN "ku"."class_year"."is_alumni" IS 'Boolean field indicating whether the class year is an "Alumni" (True) class or current class (False)';
COMMENT ON COLUMN "ku"."class_year"."sort_order" IS 'Floating point sort order field -- allows for sorting by a custom order.';
COMMENT ON COLUMN "ku"."class_year"."create_date" IS 'Date the record was created';
COMMENT ON COLUMN "ku"."class_year"."last_update_date" IS 'Date that the record was last updated';
COMMENT ON COLUMN "ku"."class_year"."updated_by_user_id" IS 'System user_id for the user/program that made the last change';

CREATE TABLE "ku"."conf" (
"row_id" serial8 NOT NULL,
"conf_name" varchar(128) NOT NULL,
"conf_text" varchar(255),
"conf_integer" int8,
"conf_decimal" decimal(12,4),
"conf_date" date,
"conf_description" varchar(512) NOT NULL,
CONSTRAINT "dbversion_pkey" PRIMARY KEY ("row_id") 
)
WITHOUT OIDS;
COMMENT ON TABLE "ku"."conf" IS 'Configuration table.   System wide values that are relevant to the database layer are stored in this table as a series of key/values with a description.';
COMMENT ON COLUMN "ku"."conf"."row_id" IS 'Serial integer, auto-generated.   Simple primary key, does not join to any other tables.';
COMMENT ON COLUMN "ku"."conf"."conf_name" IS 'Name of the configuration variable';
COMMENT ON COLUMN "ku"."conf"."conf_text" IS 'Stores the configuration variable for varchar/char parameters -- if this field has a value, conf_integer, conf_decimal and conf_date must be null';
COMMENT ON COLUMN "ku"."conf"."conf_integer" IS 'Stores the configuration variable for integer parameters -- if this field has a value, conf_text, conf_decimal and conf_date must be null';
COMMENT ON COLUMN "ku"."conf"."conf_decimal" IS 'Stores the configuration variable for decimal parameters -- if this field has a value, conf_integer, conf_text and conf_date must be null';
COMMENT ON COLUMN "ku"."conf"."conf_date" IS 'Stores the configuration variable for date parameters -- if this field has a value, conf_integer, conf_decimal and conf_text must be null';
COMMENT ON COLUMN "ku"."conf"."conf_description" IS 'Description of the conf variable -- values and usage.';

CREATE TABLE "ku"."student" (
"student_id" int4 NOT NULL,
"first_name" varchar(128) NOT NULL DEFAULT '',
"last_name" varchar(128) NOT NULL DEFAULT '',
"email" varchar(255) NOT NULL DEFAULT '',
"school_email" varchar(255),
"gender" char(1) DEFAULT '',
"dob" date,
"class_year" int4 NOT NULL,
"grad_year" int4,
"cd_ethnicity" char(5),
"cd_major" char(3),
"cd_minor" char(3),
"campus_phone" varchar(12),
"cell_phone" varchar(12),
"student_photo" varchar(64),
"active_flag" bool,
"create_date" timestamp(0),
"last_update_date" timestamp(0),
"updated_by_user_id" int8,
"optimistic_lock" int8 DEFAULT 0,
"locked_by_user_id" int8 DEFAULT 0,
CONSTRAINT "pkey_student" PRIMARY KEY ("student_id") 
)
WITHOUT OIDS;
CREATE INDEX "ndx_student_class_year" ON "ku"."student" USING btree ("class_year" ASC);
COMMENT ON TABLE "ku"."student" IS 'The student table holds the list of current students — students that are enrolled.   Students that have “graduated” from Kuromaku-U are moved to the Alumni table. ';
COMMENT ON COLUMN "ku"."student"."student_id" IS 'Student_id, primary key, starts at 1001 -- next value is max(student_id)+1';
COMMENT ON COLUMN "ku"."student"."first_name" IS 'First name of student';
COMMENT ON COLUMN "ku"."student"."last_name" IS 'Last name of student';
COMMENT ON COLUMN "ku"."student"."email" IS 'Personal email address - first initial + last_name + random number -- domains are randomly generated';
COMMENT ON COLUMN "ku"."student"."school_email" IS 'School-supplied email address - first initial + last_name + random integer "@kuromaku-u.org"';

CREATE TABLE "ku"."student_address" (
"row_id" serial8 NOT NULL,
"student_id" int4 NOT NULL,
"address_1" varchar(255),
"address_2" varchar(255),
"city" varchar(255),
"cd_state" char(2),
"province" varchar(128),
"zip_code" varchar(10),
"postal_code" varchar(24),
"cd_country" char(2),
"active_flag" bool,
"create_date" timestamp(0),
"last_update_date" timestamp(0),
"updated_by_user_id" int4,
"optimistic_lock" int4,
"locked_by_user_id" int4,
CONSTRAINT "student_address_pkey" PRIMARY KEY ("row_id") 
)
WITHOUT OIDS;
CREATE INDEX "ndx_student_address_1" ON "ku"."student_address" USING btree ("student_id" ASC);

CREATE TABLE "ku"."building" (
"building_id" varchar(16) NOT NULL,
"name" varchar(255),
"cd_building_type" int4,
"centroid_x" decimal(16,9),
"centroid_y" decimal(16,9),
"create_date" timestamp(0),
"last_update_date" timestamp(0),
"updated_by_user_id" int4,
PRIMARY KEY ("building_id") 
)
WITHOUT OIDS;
COMMENT ON TABLE "ku"."building" IS 'Buildings for the Kuromaku UI campus.  Records correspond to the Kuromaku_U_Campus_Map.jpg.   Links to the cd_building_type table for building types (Dormitories, Academic Buildings, etc).';
COMMENT ON COLUMN "ku"."building"."building_id" IS 'Building_ID is a short string version of the building name in uppercase.';
COMMENT ON COLUMN "ku"."building"."name" IS 'Full name of the building';
COMMENT ON COLUMN "ku"."building"."cd_building_type" IS 'Link go the cd_building_type table -- determines the type of building, dormitory, academic building, etc.';
COMMENT ON COLUMN "ku"."building"."centroid_x" IS 'Centroid X coordinate -- paired with Centroid Y coordinate gives you the exact location of the building on campus';
COMMENT ON COLUMN "ku"."building"."centroid_y" IS 'Centroid Y coordinate -- paired with Centroid X coordinate gives you the exact location of the building on campus';
COMMENT ON COLUMN "ku"."building"."create_date" IS 'Date the record was created';
COMMENT ON COLUMN "ku"."building"."last_update_date" IS 'Date that the record was last updated';
COMMENT ON COLUMN "ku"."building"."updated_by_user_id" IS 'System user_id for the user/program that made the last change';

CREATE TABLE "ku"."cd_building_type" (
"cd_building_type" serial4 NOT NULL,
"name_building_type" varchar(255),
"sort_order" float8,
PRIMARY KEY ("cd_building_type") 
)
WITHOUT OIDS;
COMMENT ON TABLE "ku"."cd_building_type" IS 'Code and Description table of building types — used to classify buildings, i.e. Dormitory, Library, Classrooms, etc.';
COMMENT ON COLUMN "ku"."cd_building_type"."cd_building_type" IS 'Auto generated primary key -- numeric key (dataless key).';
COMMENT ON COLUMN "ku"."cd_building_type"."name_building_type" IS 'Name of the building type (Dormitory, Library, etc)';
COMMENT ON COLUMN "ku"."cd_building_type"."sort_order" IS 'Custom sort order (allows for non-alphabetic sorts of the name)';

CREATE TABLE "ku"."cd_ethnicity" (
"cd_ethnicity" char(5) NOT NULL,
"name_ethnicity" varchar(255),
"sort_order" float8,
PRIMARY KEY ("cd_ethnicity") 
)
WITHOUT OIDS;
CREATE TABLE "ku"."cd_major" (
"cd_major" char(3) NOT NULL,
"name_major" varchar(255),
"sort_order" float8,
PRIMARY KEY ("cd_major") 
)
WITHOUT OIDS;
CREATE TABLE "ku"."cd_grade" (
"cd_grade" serial8 NOT NULL,
"letter_grade" char(2),
"numeric_grade" decimal(6,2),
PRIMARY KEY ("cd_grade") 
)
WITHOUT OIDS;
CREATE TABLE "ku"."cd_minor" (
"cd_minor" char(3) NOT NULL,
"name_minor" varchar(255),
"sort_order" float8,
PRIMARY KEY ("cd_minor") 
)
WITHOUT OIDS;
CREATE TABLE "ku"."course_catalog" (
"catnum" char(9) NOT NULL,
"cd_major_minor" char(3),
"course_title" varchar(128),
"course_desc" varchar(2048),
"course_type" char(3),
"units" int,
"active_flag" bool,
"create_date" timestamp(0),
"last_update_date" timestamp(0),
"updated_by_user_id" int4,
"optimistic_lock" int4,
"locked_by_user_id" int4,
PRIMARY KEY ("catnum") 
)
WITHOUT OIDS;
CREATE TABLE "ku"."semester" (
"semester_id" serial8 NOT NULL,
"semester_name" varchar(32) NOT NULL,
"academic_year_start" int8 NOT NULL,
"academic_year_end" int8 NOT NULL,
"semester_start_date" date NOT NULL,
"semester_end_date" date NOT NULL,
"is_current" bool NOT NULL,
PRIMARY KEY ("semester_id") 
)
WITHOUT OIDS;
CREATE TABLE "ku"."cd_country" (
"cd_country" char(2) NOT NULL,
"name_country" varchar(255),
"sort_order" float8,
PRIMARY KEY ("cd_country") 
)
WITHOUT OIDS;
CREATE TABLE "ku"."cd_state" (
"cd_state" char(2) NOT NULL,
"name_state" varchar(255),
"fips" int8,
"standard_federal_region" char(5),
"census_region" int8,
"census_region_name" varchar(32),
"census_division" int8,
"census_division_name" varchar(128),
"circuit_court" int8,
"sort_order" float8,
PRIMARY KEY ("cd_state") 
)
WITHOUT OIDS;
COMMENT ON COLUMN "ku"."cd_state"."cd_state" IS 'State codes, state names and federal data for each state';

CREATE TABLE "ku"."db_version" (
"row_id" serial8 NOT NULL,
"db_version_number" decimal(10,2) NOT NULL,
"db_version_date" date NOT NULL,
"db_version_desc" varchar(512) NOT NULL,
PRIMARY KEY ("row_id") 
)
WITHOUT OIDS;
COMMENT ON TABLE "ku"."db_version" IS 'ku.db_version tracks database changes.  It provides a log history of changes that we make to the design and data in the sample KU database.  Allows you to compare the version that you have installed with the latest version of the database.  This entire schema will be checked into Github, with detailed check-in messages for changes.  This table keeps a record of the db specific changes so you can check your “version” of the database with a simple query.';
COMMENT ON COLUMN "ku"."db_version"."row_id" IS 'Serial integer, auto-generated.   Simple primary key, does not join to any other tables.';
COMMENT ON COLUMN "ku"."db_version"."db_version_number" IS 'Version number.  Numbers to the right indicate minor changes, numbers to the left of the decimal indicate larger changes';
COMMENT ON COLUMN "ku"."db_version"."db_version_date" IS 'Date that the version was pushed out.';
COMMENT ON COLUMN "ku"."db_version"."db_version_desc" IS 'Short description of the database change.';

CREATE TABLE "ku"."building_distance" (
"row_id" serial8 NOT NULL,
"building_id" varchar(16) NOT NULL,
"target_building_id" varchar(16) NOT NULL,
"distance_in_meters" decimal(16,9),
"create_date" timestamp(0),
"last_update_date" timestamp(0),
"updated_by_user_id" int4,
PRIMARY KEY ("row_id") 
)
WITHOUT OIDS;
COMMENT ON TABLE "ku"."building_distance" IS 'This table shows the calculated distance, in meters as the crow flies, between any two buildings on the campus.  [You could calculate these values using the centroid_x_ and centroid_y values on the building table.  Since buildings do not generally “move”, we pre-calculated them here]';
COMMENT ON COLUMN "ku"."building_distance"."row_id" IS 'Auto generated serial row id.   Table does not join to any other tables by this value, it is simply a unique row id to be used for updates.  ';
COMMENT ON COLUMN "ku"."building_distance"."building_id" IS 'Building_id, joins to the Building table.';
COMMENT ON COLUMN "ku"."building_distance"."target_building_id" IS 'Target building id, joins to the building table by the building_id on the building table. ';
COMMENT ON COLUMN "ku"."building_distance"."distance_in_meters" IS 'Distance, in meters, as the crow flies, between building_id and target_building_id';
COMMENT ON COLUMN "ku"."building_distance"."create_date" IS 'Date the record was created';
COMMENT ON COLUMN "ku"."building_distance"."last_update_date" IS 'Date that the record was last updated';
COMMENT ON COLUMN "ku"."building_distance"."updated_by_user_id" IS 'System user_id for the user/program that made the last change';


ALTER TABLE "ku"."student_address" ADD CONSTRAINT "fk_student_address_student" FOREIGN KEY ("student_id") REFERENCES "ku"."student" ("student_id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "ku"."building" ADD CONSTRAINT "fk_ku_building" FOREIGN KEY ("cd_building_type") REFERENCES "ku"."cd_building_type" ("cd_building_type") ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE "ku"."student" ADD CONSTRAINT "fk_ethnicity" FOREIGN KEY ("cd_ethnicity") REFERENCES "ku"."cd_ethnicity" ("cd_ethnicity") ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE "ku"."student" ADD CONSTRAINT "fk_major" FOREIGN KEY ("cd_major") REFERENCES "ku"."cd_major" ("cd_major") ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE "ku"."student" ADD CONSTRAINT "fk_minor" FOREIGN KEY ("cd_minor") REFERENCES "ku"."cd_minor" ("cd_minor") ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE "ku"."student" ADD CONSTRAINT "fk_student_class_year" FOREIGN KEY ("class_year") REFERENCES "ku"."class_year" ("class_year") ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE "ku"."student_address" ADD CONSTRAINT "fk_student_address_cd_country" FOREIGN KEY ("cd_country") REFERENCES "ku"."cd_country" ("cd_country") ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE "ku"."student_address" ADD CONSTRAINT "fk_student_address_cd_state" FOREIGN KEY ("cd_state") REFERENCES "ku"."cd_state" ("cd_state") ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE "ku"."building_distance" ADD CONSTRAINT "fk_building_distance_1" FOREIGN KEY ("building_id") REFERENCES "ku"."building" ("building_id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "ku"."building_distance" ADD CONSTRAINT "fk_building_distance2" FOREIGN KEY ("target_building_id") REFERENCES "ku"."building" ("building_id") ON DELETE NO ACTION ON UPDATE NO ACTION;

