"""Database migration utilities for new v2 features"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def migrate_to_v2(db: AsyncSession):
    """
    Create all new tables for V2 features:
    - Surveyor & Survey tables
    - StorePhoto table
    - CategoryImage table
    - AdvertisementSpot & PromotionalOffer tables
    - AdminRole & RolePermission tables
    - AuditLog table
    """

    # Create Surveyor table
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS surveyors (
            id VARCHAR PRIMARY KEY,
            user_id VARCHAR UNIQUE NOT NULL,
            surveyor_code VARCHAR(20) UNIQUE NOT NULL,
            region VARCHAR(100),
            city VARCHAR(100),
            quartier VARCHAR(100),
            is_active BOOLEAN DEFAULT TRUE,
            sync_status VARCHAR(20) DEFAULT 'synced',
            last_sync TIMESTAMP WITH TIME ZONE,
            total_stores_surveyed INTEGER DEFAULT 0,
            verification_score FLOAT DEFAULT 0.0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE INDEX idx_surveyors_user_id ON surveyors(user_id);
        CREATE INDEX idx_surveyors_surveyor_code ON surveyors(surveyor_code);
    """))

    # Create Survey table
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS surveys (
            id VARCHAR PRIMARY KEY,
            surveyor_id VARCHAR NOT NULL,
            commerce_id VARCHAR,
            store_name VARCHAR(150) NOT NULL,
            owner_name VARCHAR(150),
            category_id VARCHAR NOT NULL,
            subcategory_id VARCHAR,
            phone VARCHAR(20),
            address VARCHAR(250),
            city VARCHAR(100),
            quartier VARCHAR(100),
            latitude FLOAT NOT NULL,
            longitude FLOAT NOT NULL,
            gps_accuracy FLOAT,
            description TEXT,
            opening_hours JSONB,
            availability VARCHAR(100),
            services JSONB DEFAULT '[]',
            tags JSONB DEFAULT '[]',
            status VARCHAR(20) DEFAULT 'pending',
            is_active BOOLEAN DEFAULT TRUE,
            survey_date TIMESTAMP WITH TIME ZONE NOT NULL,
            synced_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE,
            FOREIGN KEY(surveyor_id) REFERENCES surveyors(id),
            FOREIGN KEY(commerce_id) REFERENCES commerces(id),
            FOREIGN KEY(category_id) REFERENCES categories(id)
        );
        CREATE INDEX idx_surveys_surveyor_id ON surveys(surveyor_id);
        CREATE INDEX idx_surveys_status ON surveys(status);
    """))

    # Create SurveyPhoto table
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS survey_photos (
            id VARCHAR PRIMARY KEY,
            survey_id VARCHAR NOT NULL,
            photo_url VARCHAR NOT NULL,
            photo_type VARCHAR(50) DEFAULT 'storefront',
            uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(survey_id) REFERENCES surveys(id)
        );
        CREATE INDEX idx_survey_photos_survey_id ON survey_photos(survey_id);
    """))

    # Create StorePhoto table
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS store_photos (
            id VARCHAR PRIMARY KEY,
            commerce_id VARCHAR NOT NULL,
            photo_url VARCHAR NOT NULL,
            photo_type VARCHAR(50) DEFAULT 'storefront',
            is_cover BOOLEAN DEFAULT FALSE,
            display_order INTEGER DEFAULT 0,
            uploaded_by VARCHAR,
            uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(commerce_id) REFERENCES commerces(id),
            FOREIGN KEY(uploaded_by) REFERENCES users(id)
        );
        CREATE INDEX idx_store_photos_commerce_id ON store_photos(commerce_id);
        CREATE INDEX idx_store_photos_is_cover ON store_photos(is_cover);
    """))

    # Create CategoryImage table
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS category_images (
            id VARCHAR PRIMARY KEY,
            category_id VARCHAR NOT NULL,
            image_url VARCHAR NOT NULL,
            image_type VARCHAR(50) DEFAULT 'cover',
            display_order INTEGER DEFAULT 0,
            uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(category_id) REFERENCES categories(id)
        );
        CREATE INDEX idx_category_images_category_id ON category_images(category_id);
    """))

    # Create AdvertisementSpot table
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS advertisement_spots (
            id VARCHAR PRIMARY KEY,
            placement VARCHAR(100) NOT NULL,
            position INTEGER DEFAULT 0,
            width INTEGER DEFAULT 360,
            height INTEGER DEFAULT 200,
            is_available BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX idx_advertisement_spots_placement ON advertisement_spots(placement);
    """))

    # Create PromotionalOffer table
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS promotional_offers (
            id VARCHAR PRIMARY KEY,
            commerce_id VARCHAR NOT NULL,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            image_url VARCHAR,
            discount_percent INTEGER,
            discount_amount_fcfa INTEGER,
            code VARCHAR(50) UNIQUE,
            starts_at TIMESTAMP WITH TIME ZONE NOT NULL,
            ends_at TIMESTAMP WITH TIME ZONE NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            view_count BIGINT DEFAULT 0,
            click_count BIGINT DEFAULT 0,
            usage_count INTEGER DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(commerce_id) REFERENCES commerces(id)
        );
        CREATE INDEX idx_promotional_offers_commerce_id ON promotional_offers(commerce_id);
        CREATE INDEX idx_promotional_offers_is_active ON promotional_offers(is_active);
    """))

    # Create AdminRole table
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS admin_roles (
            id VARCHAR PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL,
            role_type VARCHAR(50) NOT NULL,
            description TEXT,
            is_custom BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """))

    # Create RolePermission table
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS role_permissions (
            id VARCHAR PRIMARY KEY,
            admin_role_id VARCHAR NOT NULL,
            permission VARCHAR(100) NOT NULL,
            is_granted BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(admin_role_id) REFERENCES admin_roles(id)
        );
        CREATE INDEX idx_role_permissions_admin_role_id ON role_permissions(admin_role_id);
    """))

    # Create AuditLog table
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id VARCHAR PRIMARY KEY,
            admin_id VARCHAR NOT NULL,
            action VARCHAR(100) NOT NULL,
            resource_type VARCHAR(100) NOT NULL,
            resource_id VARCHAR NOT NULL,
            changes JSONB,
            status VARCHAR(50) DEFAULT 'success',
            ip_address VARCHAR(50),
            user_agent VARCHAR,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(admin_id) REFERENCES users(id)
        );
        CREATE INDEX idx_audit_logs_admin_id ON audit_logs(admin_id);
        CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
    """))

    await db.commit()
    print("✅ All V2 migration tables created successfully!")
