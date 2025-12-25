[
    {
        "id": "pbc_3142635823",
        "listRule": null,
        "viewRule": null,
        "createRule": null,
        "updateRule": null,
        "deleteRule": null,
        "name": "_superusers",
        "type": "auth",
        "fields": [
            {
                "autogeneratePattern": "[a-z0-9]{15}",
                "hidden": false,
                "id": "text3208210256",
                "max": 15,
                "min": 15,
                "name": "id",
                "pattern": "^[a-z0-9]+$",
                "presentable": false,
                "primaryKey": true,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "cost": 0,
                "hidden": true,
                "id": "password901924565",
                "max": 0,
                "min": 8,
                "name": "password",
                "pattern": "",
                "presentable": false,
                "required": true,
                "system": true,
                "type": "password"
            },
            {
                "autogeneratePattern": "[a-zA-Z0-9]{50}",
                "hidden": true,
                "id": "text2504183744",
                "max": 60,
                "min": 30,
                "name": "tokenKey",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "exceptDomains": null,
                "hidden": false,
                "id": "email3885137012",
                "name": "email",
                "onlyDomains": null,
                "presentable": false,
                "required": true,
                "system": true,
                "type": "email"
            },
            {
                "hidden": false,
                "id": "bool1547992806",
                "name": "emailVisibility",
                "presentable": false,
                "required": false,
                "system": true,
                "type": "bool"
            },
            {
                "hidden": false,
                "id": "bool256245529",
                "name": "verified",
                "presentable": false,
                "required": false,
                "system": true,
                "type": "bool"
            },
            {
                "hidden": false,
                "id": "autodate2990389176",
                "name": "created",
                "onCreate": true,
                "onUpdate": false,
                "presentable": false,
                "system": true,
                "type": "autodate"
            },
            {
                "hidden": false,
                "id": "autodate3332085495",
                "name": "updated",
                "onCreate": true,
                "onUpdate": true,
                "presentable": false,
                "system": true,
                "type": "autodate"
            }
        ],
        "indexes": [
            "CREATE UNIQUE INDEX `idx_tokenKey_pbc_3142635823` ON `_superusers` (`tokenKey`)",
            "CREATE UNIQUE INDEX `idx_email_pbc_3142635823` ON `_superusers` (`email`) WHERE `email` != ''"
        ],
        "system": true,
        "authRule": "",
        "manageRule": null,
        "authAlert": {
            "enabled": true,
            "emailTemplate": {
                "subject": "Login from a new location",
                "body": "<p>Hello,</p>\n<p>We noticed a login to your {APP_NAME} account from a new location.</p>\n<p>If this was you, you may disregard this email.</p>\n<p><strong>If this wasn't you, you should immediately change your {APP_NAME} account password to revoke access from all other locations.</strong></p>\n<p>\n  Thanks,<br/>\n  {APP_NAME} team\n</p>"
            }
        },
        "oauth2": {
            "mappedFields": {
                "id": "",
                "name": "",
                "username": "",
                "avatarURL": ""
            },
            "enabled": false
        },
        "passwordAuth": {
            "enabled": true,
            "identityFields": [
                "email"
            ]
        },
        "mfa": {
            "enabled": false,
            "duration": 1800,
            "rule": ""
        },
        "otp": {
            "enabled": false,
            "duration": 180,
            "length": 8,
            "emailTemplate": {
                "subject": "OTP for {APP_NAME}",
                "body": "<p>Hello,</p>\n<p>Your one-time password is: <strong>{OTP}</strong></p>\n<p><i>If you didn't ask for the one-time password, you can ignore this email.</i></p>\n<p>\n  Thanks,<br/>\n  {APP_NAME} team\n</p>"
            }
        },
        "authToken": {
            "duration": 86400
        },
        "passwordResetToken": {
            "duration": 1800
        },
        "emailChangeToken": {
            "duration": 1800
        },
        "verificationToken": {
            "duration": 259200
        },
        "fileToken": {
            "duration": 180
        },
        "verificationTemplate": {
            "subject": "Verify your {APP_NAME} email",
            "body": "<p>Hello,</p>\n<p>Thank you for joining us at {APP_NAME}.</p>\n<p>Click on the button below to verify your email address.</p>\n<p>\n  <a class=\"btn\" href=\"{APP_URL}/_/#/auth/confirm-verification/{TOKEN}\" target=\"_blank\" rel=\"noopener\">Verify</a>\n</p>\n<p>\n  Thanks,<br/>\n  {APP_NAME} team\n</p>"
        },
        "resetPasswordTemplate": {
            "subject": "Reset your {APP_NAME} password",
            "body": "<p>Hello,</p>\n<p>Click on the button below to reset your password.</p>\n<p>\n  <a class=\"btn\" href=\"{APP_URL}/_/#/auth/confirm-password-reset/{TOKEN}\" target=\"_blank\" rel=\"noopener\">Reset password</a>\n</p>\n<p><i>If you didn't ask to reset your password, you can ignore this email.</i></p>\n<p>\n  Thanks,<br/>\n  {APP_NAME} team\n</p>"
        },
        "confirmEmailChangeTemplate": {
            "subject": "Confirm your {APP_NAME} new email address",
            "body": "<p>Hello,</p>\n<p>Click on the button below to confirm your new email address.</p>\n<p>\n  <a class=\"btn\" href=\"{APP_URL}/_/#/auth/confirm-email-change/{TOKEN}\" target=\"_blank\" rel=\"noopener\">Confirm new email</a>\n</p>\n<p><i>If you didn't ask to change your email address, you can ignore this email.</i></p>\n<p>\n  Thanks,<br/>\n  {APP_NAME} team\n</p>"
        }
    },
    {
        "id": "_pb_users_auth_",
        "listRule": "id = @request.auth.id",
        "viewRule": "id = @request.auth.id",
        "createRule": "",
        "updateRule": "id = @request.auth.id",
        "deleteRule": "id = @request.auth.id",
        "name": "users",
        "type": "auth",
        "fields": [
            {
                "autogeneratePattern": "[a-z0-9]{15}",
                "hidden": false,
                "id": "text3208210256",
                "max": 15,
                "min": 15,
                "name": "id",
                "pattern": "^[a-z0-9]+$",
                "presentable": false,
                "primaryKey": true,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "cost": 0,
                "hidden": true,
                "id": "password901924565",
                "max": 0,
                "min": 8,
                "name": "password",
                "pattern": "",
                "presentable": false,
                "required": true,
                "system": true,
                "type": "password"
            },
            {
                "autogeneratePattern": "[a-zA-Z0-9]{50}",
                "hidden": true,
                "id": "text2504183744",
                "max": 60,
                "min": 30,
                "name": "tokenKey",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "exceptDomains": null,
                "hidden": false,
                "id": "email3885137012",
                "name": "email",
                "onlyDomains": null,
                "presentable": false,
                "required": true,
                "system": true,
                "type": "email"
            },
            {
                "hidden": false,
                "id": "bool1547992806",
                "name": "emailVisibility",
                "presentable": false,
                "required": false,
                "system": true,
                "type": "bool"
            },
            {
                "hidden": false,
                "id": "bool256245529",
                "name": "verified",
                "presentable": false,
                "required": false,
                "system": true,
                "type": "bool"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text1579384326",
                "max": 255,
                "min": 0,
                "name": "name",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": false,
                "type": "text"
            },
            {
                "hidden": false,
                "id": "autodate2990389176",
                "name": "created",
                "onCreate": true,
                "onUpdate": false,
                "presentable": false,
                "system": false,
                "type": "autodate"
            },
            {
                "hidden": false,
                "id": "autodate3332085495",
                "name": "updated",
                "onCreate": true,
                "onUpdate": true,
                "presentable": false,
                "system": false,
                "type": "autodate"
            }
        ],
        "indexes": [
            "CREATE UNIQUE INDEX `idx_tokenKey__pb_users_auth_` ON `users` (`tokenKey`)",
            "CREATE UNIQUE INDEX `idx_email__pb_users_auth_` ON `users` (`email`) WHERE `email` != ''"
        ],
        "system": false,
        "authRule": "",
        "manageRule": null,
        "authAlert": {
            "enabled": true,
            "emailTemplate": {
                "subject": "Login from a new location",
                "body": "<p>Hello,</p>\n<p>We noticed a login to your {APP_NAME} account from a new location.</p>\n<p>If this was you, you may disregard this email.</p>\n<p><strong>If this wasn't you, you should immediately change your {APP_NAME} account password to revoke access from all other locations.</strong></p>\n<p>\n  Thanks,<br/>\n  {APP_NAME} team\n</p>"
            }
        },
        "oauth2": {
            "mappedFields": {
                "id": "",
                "name": "name",
                "username": "",
                "avatarURL": ""
            },
            "enabled": false
        },
        "passwordAuth": {
            "enabled": true,
            "identityFields": [
                "email"
            ]
        },
        "mfa": {
            "enabled": false,
            "duration": 1800,
            "rule": ""
        },
        "otp": {
            "enabled": false,
            "duration": 180,
            "length": 8,
            "emailTemplate": {
                "subject": "OTP for {APP_NAME}",
                "body": "<p>Hello,</p>\n<p>Your one-time password is: <strong>{OTP}</strong></p>\n<p><i>If you didn't ask for the one-time password, you can ignore this email.</i></p>\n<p>\n  Thanks,<br/>\n  {APP_NAME} team\n</p>"
            }
        },
        "authToken": {
            "duration": 604800
        },
        "passwordResetToken": {
            "duration": 1800
        },
        "emailChangeToken": {
            "duration": 1800
        },
        "verificationToken": {
            "duration": 259200
        },
        "fileToken": {
            "duration": 180
        },
        "verificationTemplate": {
            "subject": "Verify your {APP_NAME} email",
            "body": "<p>Hello,</p>\n<p>Thank you for joining us at {APP_NAME}.</p>\n<p>Click on the button below to verify your email address.</p>\n<p>\n  <a class=\"btn\" href=\"{APP_URL}/_/#/auth/confirm-verification/{TOKEN}\" target=\"_blank\" rel=\"noopener\">Verify</a>\n</p>\n<p>\n  Thanks,<br/>\n  {APP_NAME} team\n</p>"
        },
        "resetPasswordTemplate": {
            "subject": "Reset your {APP_NAME} password",
            "body": "<p>Hello,</p>\n<p>Click on the button below to reset your password.</p>\n<p>\n  <a class=\"btn\" href=\"{APP_URL}/_/#/auth/confirm-password-reset/{TOKEN}\" target=\"_blank\" rel=\"noopener\">Reset password</a>\n</p>\n<p><i>If you didn't ask to reset your password, you can ignore this email.</i></p>\n<p>\n  Thanks,<br/>\n  {APP_NAME} team\n</p>"
        },
        "confirmEmailChangeTemplate": {
            "subject": "Confirm your {APP_NAME} new email address",
            "body": "<p>Hello,</p>\n<p>Click on the button below to confirm your new email address.</p>\n<p>\n  <a class=\"btn\" href=\"{APP_URL}/_/#/auth/confirm-email-change/{TOKEN}\" target=\"_blank\" rel=\"noopener\">Confirm new email</a>\n</p>\n<p><i>If you didn't ask to change your email address, you can ignore this email.</i></p>\n<p>\n  Thanks,<br/>\n  {APP_NAME} team\n</p>"
        }
    },
    {
        "id": "pbc_4275539003",
        "listRule": "@request.auth.id != '' && recordRef = @request.auth.id && collectionRef = @request.auth.collectionId",
        "viewRule": "@request.auth.id != '' && recordRef = @request.auth.id && collectionRef = @request.auth.collectionId",
        "createRule": null,
        "updateRule": null,
        "deleteRule": "@request.auth.id != '' && recordRef = @request.auth.id && collectionRef = @request.auth.collectionId",
        "name": "_authOrigins",
        "type": "base",
        "fields": [
            {
                "autogeneratePattern": "[a-z0-9]{15}",
                "hidden": false,
                "id": "text3208210256",
                "max": 15,
                "min": 15,
                "name": "id",
                "pattern": "^[a-z0-9]+$",
                "presentable": false,
                "primaryKey": true,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text455797646",
                "max": 0,
                "min": 0,
                "name": "collectionRef",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text127846527",
                "max": 0,
                "min": 0,
                "name": "recordRef",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text4228609354",
                "max": 0,
                "min": 0,
                "name": "fingerprint",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "hidden": false,
                "id": "autodate2990389176",
                "name": "created",
                "onCreate": true,
                "onUpdate": false,
                "presentable": false,
                "system": true,
                "type": "autodate"
            },
            {
                "hidden": false,
                "id": "autodate3332085495",
                "name": "updated",
                "onCreate": true,
                "onUpdate": true,
                "presentable": false,
                "system": true,
                "type": "autodate"
            }
        ],
        "indexes": [
            "CREATE UNIQUE INDEX `idx_authOrigins_unique_pairs` ON `_authOrigins` (collectionRef, recordRef, fingerprint)"
        ],
        "system": true
    },
    {
        "id": "pbc_2281828961",
        "listRule": "@request.auth.id != '' && recordRef = @request.auth.id && collectionRef = @request.auth.collectionId",
        "viewRule": "@request.auth.id != '' && recordRef = @request.auth.id && collectionRef = @request.auth.collectionId",
        "createRule": null,
        "updateRule": null,
        "deleteRule": "@request.auth.id != '' && recordRef = @request.auth.id && collectionRef = @request.auth.collectionId",
        "name": "_externalAuths",
        "type": "base",
        "fields": [
            {
                "autogeneratePattern": "[a-z0-9]{15}",
                "hidden": false,
                "id": "text3208210256",
                "max": 15,
                "min": 15,
                "name": "id",
                "pattern": "^[a-z0-9]+$",
                "presentable": false,
                "primaryKey": true,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text455797646",
                "max": 0,
                "min": 0,
                "name": "collectionRef",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text127846527",
                "max": 0,
                "min": 0,
                "name": "recordRef",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text2462348188",
                "max": 0,
                "min": 0,
                "name": "provider",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text1044722854",
                "max": 0,
                "min": 0,
                "name": "providerId",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "hidden": false,
                "id": "autodate2990389176",
                "name": "created",
                "onCreate": true,
                "onUpdate": false,
                "presentable": false,
                "system": true,
                "type": "autodate"
            },
            {
                "hidden": false,
                "id": "autodate3332085495",
                "name": "updated",
                "onCreate": true,
                "onUpdate": true,
                "presentable": false,
                "system": true,
                "type": "autodate"
            }
        ],
        "indexes": [
            "CREATE UNIQUE INDEX `idx_externalAuths_record_provider` ON `_externalAuths` (collectionRef, recordRef, provider)",
            "CREATE UNIQUE INDEX `idx_externalAuths_collection_provider` ON `_externalAuths` (collectionRef, provider, providerId)"
        ],
        "system": true
    },
    {
        "id": "pbc_2279338944",
        "listRule": "@request.auth.id != '' && recordRef = @request.auth.id && collectionRef = @request.auth.collectionId",
        "viewRule": "@request.auth.id != '' && recordRef = @request.auth.id && collectionRef = @request.auth.collectionId",
        "createRule": null,
        "updateRule": null,
        "deleteRule": null,
        "name": "_mfas",
        "type": "base",
        "fields": [
            {
                "autogeneratePattern": "[a-z0-9]{15}",
                "hidden": false,
                "id": "text3208210256",
                "max": 15,
                "min": 15,
                "name": "id",
                "pattern": "^[a-z0-9]+$",
                "presentable": false,
                "primaryKey": true,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text455797646",
                "max": 0,
                "min": 0,
                "name": "collectionRef",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text127846527",
                "max": 0,
                "min": 0,
                "name": "recordRef",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text1582905952",
                "max": 0,
                "min": 0,
                "name": "method",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "hidden": false,
                "id": "autodate2990389176",
                "name": "created",
                "onCreate": true,
                "onUpdate": false,
                "presentable": false,
                "system": true,
                "type": "autodate"
            },
            {
                "hidden": false,
                "id": "autodate3332085495",
                "name": "updated",
                "onCreate": true,
                "onUpdate": true,
                "presentable": false,
                "system": true,
                "type": "autodate"
            }
        ],
        "indexes": [
            "CREATE INDEX `idx_mfas_collectionRef_recordRef` ON `_mfas` (collectionRef,recordRef)"
        ],
        "system": true
    },
    {
        "id": "pbc_1638494021",
        "listRule": "@request.auth.id != '' && recordRef = @request.auth.id && collectionRef = @request.auth.collectionId",
        "viewRule": "@request.auth.id != '' && recordRef = @request.auth.id && collectionRef = @request.auth.collectionId",
        "createRule": null,
        "updateRule": null,
        "deleteRule": null,
        "name": "_otps",
        "type": "base",
        "fields": [
            {
                "autogeneratePattern": "[a-z0-9]{15}",
                "hidden": false,
                "id": "text3208210256",
                "max": 15,
                "min": 15,
                "name": "id",
                "pattern": "^[a-z0-9]+$",
                "presentable": false,
                "primaryKey": true,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text455797646",
                "max": 0,
                "min": 0,
                "name": "collectionRef",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text127846527",
                "max": 0,
                "min": 0,
                "name": "recordRef",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "cost": 8,
                "hidden": true,
                "id": "password901924565",
                "max": 0,
                "min": 0,
                "name": "password",
                "pattern": "",
                "presentable": false,
                "required": true,
                "system": true,
                "type": "password"
            },
            {
                "autogeneratePattern": "",
                "hidden": true,
                "id": "text3866985172",
                "max": 0,
                "min": 0,
                "name": "sentTo",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": true,
                "type": "text"
            },
            {
                "hidden": false,
                "id": "autodate2990389176",
                "name": "created",
                "onCreate": true,
                "onUpdate": false,
                "presentable": false,
                "system": true,
                "type": "autodate"
            },
            {
                "hidden": false,
                "id": "autodate3332085495",
                "name": "updated",
                "onCreate": true,
                "onUpdate": true,
                "presentable": false,
                "system": true,
                "type": "autodate"
            }
        ],
        "indexes": [
            "CREATE INDEX `idx_otps_collectionRef_recordRef` ON `_otps` (collectionRef, recordRef)"
        ],
        "system": true
    },
    {
        "id": "pbc_2324088501",
        "listRule": "",
        "viewRule": "",
        "createRule": "@request.auth.id != \"\"",
        "updateRule": "",
        "deleteRule": "",
        "name": "accounts",
        "type": "base",
        "fields": [
            {
                "autogeneratePattern": "[a-z0-9]{15}",
                "hidden": false,
                "id": "text3208210256",
                "max": 15,
                "min": 15,
                "name": "id",
                "pattern": "^[a-z0-9]+$",
                "presentable": false,
                "primaryKey": true,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "hidden": false,
                "id": "autodate2990389176",
                "name": "created",
                "onCreate": true,
                "onUpdate": false,
                "presentable": false,
                "system": false,
                "type": "autodate"
            },
            {
                "hidden": false,
                "id": "autodate3332085495",
                "name": "updated",
                "onCreate": true,
                "onUpdate": true,
                "presentable": false,
                "system": false,
                "type": "autodate"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text2918445923",
                "max": 0,
                "min": 0,
                "name": "data",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": false,
                "type": "text"
            },
            {
                "hidden": false,
                "id": "number_price",
                "max": null,
                "min": null,
                "name": "price",
                "onlyInt": false,
                "presentable": false,
                "required": false,
                "system": false,
                "type": "number"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text_currency",
                "max": 0,
                "min": 0,
                "name": "currency",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": false,
                "type": "text"
            },
            {
                "cascadeDelete": false,
                "collectionId": "pbc_3292755704",
                "hidden": false,
                "id": "relation_category",
                "maxSelect": 1,
                "minSelect": 0,
                "name": "category",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "relation"
            },
            {
                "cascadeDelete": false,
                "collectionId": "pbc_2354486458",
                "hidden": false,
                "id": "relation_subcategory",
                "maxSelect": 1,
                "minSelect": 0,
                "name": "subcategory",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "relation"
            },
            {
                "convertURLs": false,
                "hidden": false,
                "id": "editor_metadata",
                "maxSize": 0,
                "name": "metadata",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "editor"
            },
            {
                "hidden": false,
                "id": "bool2563956121",
                "name": "sold",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "bool"
            },
            {
                "cascadeDelete": false,
                "collectionId": "pbc_4092854851",
                "hidden": false,
                "id": "relation3544843437",
                "maxSelect": 1,
                "minSelect": 0,
                "name": "product",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "relation"
            }
        ],
        "indexes": [],
        "system": false
    },
    {
        "id": "pbc_1760000006",
        "listRule": null,
        "viewRule": null,
        "createRule": null,
        "updateRule": null,
        "deleteRule": null,
        "name": "audit_logs",
        "type": "base",
        "fields": [
            {
                "autogeneratePattern": "[a-z0-9]{15}",
                "hidden": false,
                "id": "text_audit_id",
                "max": 15,
                "min": 15,
                "name": "id",
                "pattern": "^[a-z0-9]+$",
                "presentable": false,
                "primaryKey": true,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "hidden": false,
                "id": "autodate_audit_created",
                "name": "created",
                "onCreate": true,
                "onUpdate": false,
                "presentable": false,
                "system": false,
                "type": "autodate"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text_entity_type",
                "max": 0,
                "min": 0,
                "name": "entity_type",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": false,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text_entity_id",
                "max": 0,
                "min": 0,
                "name": "entity_id",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": false,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text_action",
                "max": 0,
                "min": 0,
                "name": "action",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": false,
                "type": "text"
            },
            {
                "convertURLs": false,
                "hidden": false,
                "id": "editor_payload",
                "maxSize": 0,
                "name": "payload",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "editor"
            }
        ],
        "indexes": [],
        "system": false
    },
    {
        "id": "pbc_3458397677",
        "listRule": "",
        "viewRule": "",
        "createRule": "",
        "updateRule": "",
        "deleteRule": "",
        "name": "bot_users",
        "type": "base",
        "fields": [
            {
                "autogeneratePattern": "[a-z0-9]{15}",
                "hidden": false,
                "id": "text3208210256",
                "max": 15,
                "min": 15,
                "name": "id",
                "pattern": "^[a-z0-9]+$",
                "presentable": false,
                "primaryKey": true,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "hidden": false,
                "id": "number2809058197",
                "max": null,
                "min": null,
                "name": "user_id",
                "onlyInt": false,
                "presentable": false,
                "required": false,
                "system": false,
                "type": "number"
            },
            {
                "cascadeDelete": false,
                "collectionId": "_pb_users_auth_",
                "hidden": false,
                "id": "relation_bot_user_user_ref",
                "maxSelect": 1,
                "minSelect": 0,
                "name": "user_ref",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "relation"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text4166911607",
                "max": 0,
                "min": 0,
                "name": "username",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": false,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text_role",
                "max": 0,
                "min": 0,
                "name": "role",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": false,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text2849095986",
                "max": 0,
                "min": 0,
                "name": "first_name",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": false,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text3356015194",
                "max": 0,
                "min": 0,
                "name": "last_name",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": false,
                "type": "text"
            },
            {
                "hidden": false,
                "id": "date2843275365",
                "max": "",
                "min": "",
                "name": "first_interaction",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "date"
            },
            {
                "hidden": false,
                "id": "date3558165700",
                "max": "",
                "min": "",
                "name": "last_activity",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "date"
            },
            {
                "hidden": false,
                "id": "bool458715613",
                "name": "is_active",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "bool"
            },
            {
                "hidden": false,
                "id": "autodate2990389176",
                "name": "created",
                "onCreate": true,
                "onUpdate": false,
                "presentable": false,
                "system": false,
                "type": "autodate"
            },
            {
                "hidden": false,
                "id": "autodate3332085495",
                "name": "updated",
                "onCreate": true,
                "onUpdate": true,
                "presentable": false,
                "system": false,
                "type": "autodate"
            }
        ],
        "indexes": [],
        "system": false
    },
    {
        "id": "pbc_1760000004",
        "listRule": null,
        "viewRule": null,
        "createRule": null,
        "updateRule": null,
        "deleteRule": null,
        "name": "cart_items",
        "type": "base",
        "fields": [
            {
                "autogeneratePattern": "[a-z0-9]{15}",
                "hidden": false,
                "id": "text_ci_id",
                "max": 15,
                "min": 15,
                "name": "id",
                "pattern": "^[a-z0-9]+$",
                "presentable": false,
                "primaryKey": true,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "hidden": false,
                "id": "autodate_ci_created",
                "name": "created",
                "onCreate": true,
                "onUpdate": false,
                "presentable": false,
                "system": false,
                "type": "autodate"
            },
            {
                "hidden": false,
                "id": "autodate_ci_updated",
                "name": "updated",
                "onCreate": true,
                "onUpdate": true,
                "presentable": false,
                "system": false,
                "type": "autodate"
            },
            {
                "cascadeDelete": false,
                "collectionId": "pbc_1760000003",
                "hidden": false,
                "id": "relation_ci_cart",
                "maxSelect": 1,
                "minSelect": 0,
                "name": "cart",
                "presentable": false,
                "required": true,
                "system": false,
                "type": "relation"
            },
            {
                "cascadeDelete": false,
                "collectionId": "pbc_4092854851",
                "hidden": false,
                "id": "relation_ci_product",
                "maxSelect": 1,
                "minSelect": 0,
                "name": "product",
                "presentable": false,
                "required": true,
                "system": false,
                "type": "relation"
            },
            {
                "hidden": false,
                "id": "number_ci_quantity",
                "max": null,
                "min": null,
                "name": "quantity",
                "onlyInt": false,
                "presentable": false,
                "required": false,
                "system": false,
                "type": "number"
            }
        ],
        "indexes": [],
        "system": false
    },
    {
        "id": "pbc_1760000003",
        "listRule": null,
        "viewRule": null,
        "createRule": null,
        "updateRule": null,
        "deleteRule": null,
        "name": "carts",
        "type": "base",
        "fields": [
            {
                "autogeneratePattern": "[a-z0-9]{15}",
                "hidden": false,
                "id": "text_cart_id",
                "max": 15,
                "min": 15,
                "name": "id",
                "pattern": "^[a-z0-9]+$",
                "presentable": false,
                "primaryKey": true,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "hidden": false,
                "id": "autodate_cart_created",
                "name": "created",
                "onCreate": true,
                "onUpdate": false,
                "presentable": false,
                "system": false,
                "type": "autodate"
            },
            {
                "hidden": false,
                "id": "autodate_cart_updated",
                "name": "updated",
                "onCreate": true,
                "onUpdate": true,
                "presentable": false,
                "system": false,
                "type": "autodate"
            },
            {
                "cascadeDelete": false,
                "collectionId": "_pb_users_auth_",
                "hidden": false,
                "id": "relation_cart_user",
                "maxSelect": 1,
                "minSelect": 0,
                "name": "user",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "relation"
            },
            {
                "convertURLs": false,
                "hidden": false,
                "id": "editor_cart_payload",
                "maxSize": 0,
                "name": "cart_payload",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "editor"
            }
        ],
        "indexes": [],
        "system": false
    },
    {
        "id": "pbc_3292755704",
        "listRule": "",
        "viewRule": "",
        "createRule": null,
        "updateRule": null,
        "deleteRule": null,
        "name": "categories",
        "type": "base",
        "fields": [
            {
                "autogeneratePattern": "[a-z0-9]{15}",
                "hidden": false,
                "id": "text3208210256",
                "max": 15,
                "min": 15,
                "name": "id",
                "pattern": "^[a-z0-9]+$",
                "presentable": false,
                "primaryKey": true,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text2324736937",
                "max": 0,
                "min": 0,
                "name": "key",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": false,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text1579384326",
                "max": 0,
                "min": 0,
                "name": "name",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": false,
                "type": "text"
            },
            {
                "hidden": false,
                "id": "number1361375778",
                "max": null,
                "min": null,
                "name": "sort",
                "onlyInt": false,
                "presentable": false,
                "required": false,
                "system": false,
                "type": "number"
            },
            {
                "hidden": false,
                "id": "autodate2990389176",
                "name": "created",
                "onCreate": true,
                "onUpdate": false,
                "presentable": false,
                "system": false,
                "type": "autodate"
            },
            {
                "hidden": false,
                "id": "autodate3332085495",
                "name": "updated",
                "onCreate": true,
                "onUpdate": true,
                "presentable": false,
                "system": false,
                "type": "autodate"
            }
        ],
        "indexes": [],
        "system": false
    },
    {
        "id": "pbc_1760000005",
        "listRule": null,
        "viewRule": null,
        "createRule": null,
        "updateRule": null,
        "deleteRule": null,
        "name": "files",
        "type": "base",
        "fields": [
            {
                "autogeneratePattern": "[a-z0-9]{15}",
                "hidden": false,
                "id": "text_file_id",
                "max": 15,
                "min": 15,
                "name": "id",
                "pattern": "^[a-z0-9]+$",
                "presentable": false,
                "primaryKey": true,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "hidden": false,
                "id": "autodate_file_created",
                "name": "created",
                "onCreate": true,
                "onUpdate": false,
                "presentable": false,
                "system": false,
                "type": "autodate"
            },
            {
                "hidden": false,
                "id": "autodate_file_updated",
                "name": "updated",
                "onCreate": true,
                "onUpdate": true,
                "presentable": false,
                "system": false,
                "type": "autodate"
            },
            {
                "cascadeDelete": false,
                "collectionId": "pbc_1760000001",
                "hidden": false,
                "id": "relation_file_order",
                "maxSelect": 1,
                "minSelect": 0,
                "name": "order",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "relation"
            },
            {
                "cascadeDelete": false,
                "collectionId": "pbc_1760000002",
                "hidden": false,
                "id": "relation_file_order_item",
                "maxSelect": 1,
                "minSelect": 0,
                "name": "order_item",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "relation"
            },
            {
                "hidden": false,
                "id": "file_file",
                "maxSelect": 1,
                "maxSize": 0,
                "mimeTypes": [],
                "name": "file",
                "presentable": false,
                "protected": false,
                "required": false,
                "system": false,
                "thumbs": null,
                "type": "file"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text_filename",
                "max": 0,
                "min": 0,
                "name": "filename",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": false,
                "type": "text"
            }
        ],
        "indexes": [],
        "system": false
    },
    {
        "id": "pbc_1760000002",
        "listRule": null,
        "viewRule": null,
        "createRule": null,
        "updateRule": null,
        "deleteRule": null,
        "name": "order_items",
        "type": "base",
        "fields": [
            {
                "autogeneratePattern": "[a-z0-9]{15}",
                "hidden": false,
                "id": "text_oi_id",
                "max": 15,
                "min": 15,
                "name": "id",
                "pattern": "^[a-z0-9]+$",
                "presentable": false,
                "primaryKey": true,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "hidden": false,
                "id": "autodate_oi_created",
                "name": "created",
                "onCreate": true,
                "onUpdate": false,
                "presentable": false,
                "system": false,
                "type": "autodate"
            },
            {
                "hidden": false,
                "id": "autodate_oi_updated",
                "name": "updated",
                "onCreate": true,
                "onUpdate": true,
                "presentable": false,
                "system": false,
                "type": "autodate"
            },
            {
                "cascadeDelete": false,
                "collectionId": "pbc_1760000001",
                "hidden": false,
                "id": "relation_oi_order",
                "maxSelect": 1,
                "minSelect": 0,
                "name": "order",
                "presentable": false,
                "required": true,
                "system": false,
                "type": "relation"
            },
            {
                "cascadeDelete": false,
                "collectionId": "pbc_4092854851",
                "hidden": false,
                "id": "relation_oi_product",
                "maxSelect": 1,
                "minSelect": 0,
                "name": "product",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "relation"
            },
            {
                "hidden": false,
                "id": "number_unit_price",
                "max": null,
                "min": null,
                "name": "unit_price",
                "onlyInt": false,
                "presentable": false,
                "required": false,
                "system": false,
                "type": "number"
            },
            {
                "hidden": false,
                "id": "number_quantity",
                "max": null,
                "min": null,
                "name": "quantity",
                "onlyInt": false,
                "presentable": false,
                "required": false,
                "system": false,
                "type": "number"
            },
            {
                "cascadeDelete": false,
                "collectionId": "pbc_2324088501",
                "hidden": false,
                "id": "relation_oi_account",
                "maxSelect": 1,
                "minSelect": 0,
                "name": "account",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "relation"
            },
            {
                "convertURLs": false,
                "hidden": false,
                "id": "editor_oi_meta",
                "maxSize": 0,
                "name": "metadata",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "editor"
            }
        ],
        "indexes": [],
        "system": false
    },
    {
        "id": "pbc_1760000001",
        "listRule": null,
        "viewRule": null,
        "createRule": null,
        "updateRule": null,
        "deleteRule": null,
        "name": "orders",
        "type": "base",
        "fields": [
            {
                "autogeneratePattern": "[a-z0-9]{15}",
                "hidden": false,
                "id": "text_ord_id",
                "max": 15,
                "min": 15,
                "name": "id",
                "pattern": "^[a-z0-9]+$",
                "presentable": false,
                "primaryKey": true,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "hidden": false,
                "id": "autodate_ord_created",
                "name": "created",
                "onCreate": true,
                "onUpdate": false,
                "presentable": false,
                "system": false,
                "type": "autodate"
            },
            {
                "hidden": false,
                "id": "autodate_ord_updated",
                "name": "updated",
                "onCreate": true,
                "onUpdate": true,
                "presentable": false,
                "system": false,
                "type": "autodate"
            },
            {
                "cascadeDelete": false,
                "collectionId": "_pb_users_auth_",
                "hidden": false,
                "id": "relation_orders_user",
                "maxSelect": 1,
                "minSelect": 0,
                "name": "user",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "relation"
            },
            {
                "cascadeDelete": false,
                "collectionId": "pbc_3458397677",
                "hidden": false,
                "id": "relation_orders_bot_user",
                "maxSelect": 1,
                "minSelect": 0,
                "name": "bot_user",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "relation"
            },
            {
                "hidden": false,
                "id": "number_total_amount",
                "max": null,
                "min": null,
                "name": "total_amount",
                "onlyInt": false,
                "presentable": false,
                "required": false,
                "system": false,
                "type": "number"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text_currency",
                "max": 0,
                "min": 0,
                "name": "currency",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": false,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text_status",
                "max": 0,
                "min": 0,
                "name": "status",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": false,
                "type": "text"
            },
            {
                "hidden": false,
                "id": "autodate_reserve_expires_at",
                "max": "",
                "min": "",
                "name": "reserve_expires_at",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "date"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text_order_number",
                "max": 0,
                "min": 0,
                "name": "order_number",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": false,
                "type": "text"
            },
            {
                "convertURLs": false,
                "hidden": false,
                "id": "editor_order_meta",
                "maxSize": 0,
                "name": "metadata",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "editor"
            }
        ],
        "indexes": [],
        "system": false
    },
    {
        "id": "pbc_631030571",
        "listRule": null,
        "viewRule": null,
        "createRule": null,
        "updateRule": null,
        "deleteRule": null,
        "name": "payments",
        "type": "base",
        "fields": [
            {
                "autogeneratePattern": "[a-z0-9]{15}",
                "hidden": false,
                "id": "text3208210256",
                "max": 15,
                "min": 15,
                "name": "id",
                "pattern": "^[a-z0-9]+$",
                "presentable": false,
                "primaryKey": true,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text696906237",
                "max": 0,
                "min": 0,
                "name": "invoice_id",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": false,
                "type": "text"
            },
            {
                "cascadeDelete": false,
                "collectionId": "pbc_1760000001",
                "hidden": false,
                "id": "relation4113142680",
                "maxSelect": 1,
                "minSelect": 0,
                "name": "order",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "relation"
            },
            {
                "cascadeDelete": false,
                "collectionId": "_pb_users_auth_",
                "hidden": false,
                "id": "relation2375276105",
                "maxSelect": 1,
                "minSelect": 0,
                "name": "user",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "relation"
            },
            {
                "hidden": false,
                "id": "number2392944706",
                "max": null,
                "min": null,
                "name": "amount",
                "onlyInt": false,
                "presentable": false,
                "required": false,
                "system": false,
                "type": "number"
            },
            {
                "hidden": false,
                "id": "autodate2990389176",
                "name": "created",
                "onCreate": true,
                "onUpdate": false,
                "presentable": false,
                "system": false,
                "type": "autodate"
            },
            {
                "hidden": false,
                "id": "autodate3332085495",
                "name": "updated",
                "onCreate": true,
                "onUpdate": true,
                "presentable": false,
                "system": false,
                "type": "autodate"
            }
        ],
        "indexes": [],
        "system": false
    },
    {
        "id": "pbc_4092854851",
        "listRule": "",
        "viewRule": "",
        "createRule": null,
        "updateRule": null,
        "deleteRule": null,
        "name": "products",
        "type": "base",
        "fields": [
            {
                "autogeneratePattern": "[a-z0-9]{15}",
                "hidden": false,
                "id": "text3208210256",
                "max": 15,
                "min": 15,
                "name": "id",
                "pattern": "^[a-z0-9]+$",
                "presentable": false,
                "primaryKey": true,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text2324736937",
                "max": 0,
                "min": 0,
                "name": "key",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": false,
                "type": "text"
            },
            {
                "cascadeDelete": false,
                "collectionId": "pbc_2354486458",
                "hidden": false,
                "id": "relation232563784",
                "maxSelect": 1,
                "minSelect": 0,
                "name": "subcategory",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "relation"
            },
            {
                "cascadeDelete": false,
                "collectionId": "pbc_946965560",
                "hidden": false,
                "id": "relation258142582",
                "maxSelect": 1,
                "minSelect": 0,
                "name": "region",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "relation"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text724990059",
                "max": 0,
                "min": 0,
                "name": "title",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": false,
                "type": "text"
            },
            {
                "hidden": false,
                "id": "number3402113753",
                "max": null,
                "min": null,
                "name": "price",
                "onlyInt": false,
                "presentable": false,
                "required": false,
                "system": false,
                "type": "number"
            },
            {
                "hidden": false,
                "id": "autodate2990389176",
                "name": "created",
                "onCreate": true,
                "onUpdate": false,
                "presentable": false,
                "system": false,
                "type": "autodate"
            },
            {
                "hidden": false,
                "id": "autodate3332085495",
                "name": "updated",
                "onCreate": true,
                "onUpdate": true,
                "presentable": false,
                "system": false,
                "type": "autodate"
            }
        ],
        "indexes": [],
        "system": false
    },
    {
        "id": "pbc_946965560",
        "listRule": "",
        "viewRule": "",
        "createRule": null,
        "updateRule": null,
        "deleteRule": null,
        "name": "regions",
        "type": "base",
        "fields": [
            {
                "autogeneratePattern": "[a-z0-9]{15}",
                "hidden": false,
                "id": "text3208210256",
                "max": 15,
                "min": 15,
                "name": "id",
                "pattern": "^[a-z0-9]+$",
                "presentable": false,
                "primaryKey": true,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text2324736937",
                "max": 0,
                "min": 0,
                "name": "key",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": false,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text1579384326",
                "max": 0,
                "min": 0,
                "name": "name",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": false,
                "type": "text"
            },
            {
                "hidden": false,
                "id": "autodate2990389176",
                "name": "created",
                "onCreate": true,
                "onUpdate": false,
                "presentable": false,
                "system": false,
                "type": "autodate"
            },
            {
                "hidden": false,
                "id": "autodate3332085495",
                "name": "updated",
                "onCreate": true,
                "onUpdate": true,
                "presentable": false,
                "system": false,
                "type": "autodate"
            }
        ],
        "indexes": [],
        "system": false
    },
    {
        "id": "pbc_997979991",
        "listRule": "",
        "viewRule": "",
        "createRule": "",
        "updateRule": "",
        "deleteRule": "",
        "name": "sold_accounts",
        "type": "base",
        "fields": [
            {
                "autogeneratePattern": "[a-z0-9]{15}",
                "hidden": false,
                "id": "text3208210256",
                "max": 15,
                "min": 15,
                "name": "id",
                "pattern": "^[a-z0-9]+$",
                "presentable": false,
                "primaryKey": true,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "cascadeDelete": false,
                "collectionId": "pbc_2324088501",
                "hidden": false,
                "id": "relation2100713124",
                "maxSelect": 1,
                "minSelect": 0,
                "name": "account",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "relation"
            },
            {
                "hidden": false,
                "id": "date497472529",
                "max": "",
                "min": "",
                "name": "sold_at",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "date"
            },
            {
                "hidden": false,
                "id": "date261981154",
                "max": "",
                "min": "",
                "name": "expires_at",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "date"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text2918445923",
                "max": 0,
                "min": 0,
                "name": "data",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": false,
                "type": "text"
            },
            {
                "cascadeDelete": false,
                "collectionId": "pbc_4092854851",
                "hidden": false,
                "id": "relation3544843437",
                "maxSelect": 1,
                "minSelect": 0,
                "name": "product",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "relation"
            },
            {
                "hidden": false,
                "id": "autodate2990389176",
                "name": "created",
                "onCreate": true,
                "onUpdate": false,
                "presentable": false,
                "system": false,
                "type": "autodate"
            },
            {
                "hidden": false,
                "id": "autodate3332085495",
                "name": "updated",
                "onCreate": true,
                "onUpdate": true,
                "presentable": false,
                "system": false,
                "type": "autodate"
            }
        ],
        "indexes": [],
        "system": false
    },
    {
        "id": "pbc_2354486458",
        "listRule": "",
        "viewRule": "",
        "createRule": null,
        "updateRule": null,
        "deleteRule": null,
        "name": "subcategories",
        "type": "base",
        "fields": [
            {
                "autogeneratePattern": "[a-z0-9]{15}",
                "hidden": false,
                "id": "text3208210256",
                "max": 15,
                "min": 15,
                "name": "id",
                "pattern": "^[a-z0-9]+$",
                "presentable": false,
                "primaryKey": true,
                "required": true,
                "system": true,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text2324736937",
                "max": 0,
                "min": 0,
                "name": "key",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": false,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text724990059",
                "max": 0,
                "min": 0,
                "name": "title",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": false,
                "type": "text"
            },
            {
                "autogeneratePattern": "",
                "hidden": false,
                "id": "text1843675174",
                "max": 0,
                "min": 0,
                "name": "description",
                "pattern": "",
                "presentable": false,
                "primaryKey": false,
                "required": false,
                "system": false,
                "type": "text"
            },
            {
                "cascadeDelete": false,
                "collectionId": "pbc_3292755704",
                "hidden": false,
                "id": "relation105650625",
                "maxSelect": 1,
                "minSelect": 0,
                "name": "category",
                "presentable": false,
                "required": false,
                "system": false,
                "type": "relation"
            },
            {
                "hidden": false,
                "id": "number1361375778",
                "max": null,
                "min": null,
                "name": "sort",
                "onlyInt": false,
                "presentable": false,
                "required": false,
                "system": false,
                "type": "number"
            },
            {
                "hidden": false,
                "id": "autodate2990389176",
                "name": "created",
                "onCreate": true,
                "onUpdate": false,
                "presentable": false,
                "system": false,
                "type": "autodate"
            },
            {
                "hidden": false,
                "id": "autodate3332085495",
                "name": "updated",
                "onCreate": true,
                "onUpdate": true,
                "presentable": false,
                "system": false,
                "type": "autodate"
            }
        ],
        "indexes": [],
        "system": false
    }
]