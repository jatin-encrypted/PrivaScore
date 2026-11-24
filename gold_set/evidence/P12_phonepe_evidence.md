# Evidence packet: P12 phonepe

- Source: https://www.phonepe.com/privacy-policy/  
- Fetched (UTC): 2026-11-11T18:47:35+00:00; evaluated scope: `all_users`  
- Snapshot: `policies/text/P12_phonepe.txt` sha256 `3e9c49e54dea82e7…`; 219 paragraphs, 332 sentences  
- Full numbered text: `P12_phonepe_numbered.md`

Read with `ANNOTATION_GUIDELINES.md` open. Candidates are ranked by how many different search terms match (core terms count 3, support terms 1) and shown in document order. **A missing hit is not proof of absence**: check the headings in the numbered text before labelling a flag Absent.

---

## G1 `first_party_collection_scope` (exposure, weight 1)

**Question:** What personal data does the company itself collect, and how broad is it?

**Searches run** (sentences matched):  
we collect [core]: **3**; information/data we collect [core]: **0**; collected automatically [core]: **0**; you provide [core]: **1**; location [support]: **3**; device / identifiers [support]: **2**; content / messages [support]: **6**; contacts [support]: **11**; sensitive / biometric / financial [support]: **30**; from other sources [support]: **1**; usage / log data [support]: **0**

Terms with no hits: information/data we collect, collected automatically, usage / log data

**Candidates:** 6 found, 6 shown

- **`p025.s1`** · _Information Collection_ · matched: we collect
  > ‹prev› Information Collection
  > **We may collect your Personal Information when you use our services or Platform or otherwise interact with us during the course of our relationship.**
  > ‹next› We collect Personal Information which is relevant and absolutely necessary for providing the services requested by you, offering other services / products, including in partnerships with third parties, and to continually improve the PhonePe Platform.

- **`p025.s2`** · _Information Collection_ · matched: we collect
  > ‹prev› We may collect your Personal Information when you use our services or Platform or otherwise interact with us during the course of our relationship.
  > **We collect Personal Information which is relevant and absolutely necessary for providing the services requested by you, offering other services / products, including in partnerships with third parties, and to continually improve the PhonePe Platform.**
  > ‹next› Personal and Sensitive Personal Information collected, as applicable, includes, but are not limited to:

- **`p031.s1`** · _Information Collection_ · matched: location (s), device / identifiers (s)
  > ‹prev› balance including broker ledger balance or margins, transaction history and value, bank account details, wallet balance, investment details and transactions, income range, expense range, investment goals, service or transaction related communication, order details, service fulfilment details, part of your card details for smooth transaction using PhonePe or any of the services
  > **your device details such as device identifier, internet bandwidth, mobile device model, browser plug-ins, and cookies or similar technologies that may identify your browser/PhonePe Applications and plug-ins, and time spent, IP address and location**
  > ‹next› your Short Messaging Service (SMS(es)) that are stored on your device for the purposes of, including but not limited to, registering you and your device for payments or investment services, OTPs for logins and payments, enhancing your security, bill payments and recharge reminders, and any other legitimate uses with your explicit consent

- **`p034.s1`** · _Information Collection_ · matched: location (s), content / messages (s), sensitive / biometric / financial (s)
  > ‹prev› your health and lifestyle-related information, including your physical activity, when you opt for health-tracking services
  > **video, photo, audio, and location, based on your explicit consent through your app permissions (camera, microphone, location) when you opt for a product whose core functionality can be delivered only after accessing your app permissions, or where access is as per regulatory requirements, e.g., video-based KYC, self-inspection of your vehicle, and onboarding**
  > ‹next› Information may be collected at various stages of your usage of the PhonePe Platform such as:

- **`p105.s3`** · _Third-Party Products, Services, or Websites_ · matched: you provide, location (s)
  > ‹prev› Such websites or applications are governed by their respective privacy policies, which are beyond our control.
  > **Once you leave our servers (you can tell where you are by checking the URL in the location bar on your browser or on the m-site you are redirected to), use of any Personal Information that you provide on these websites or applications is governed by the privacy policy of the operator of the application/website, you are visiting.**
  > ‹next› That policy may differ from ours and you are requested to review those policies or seek access to the policies from the domain owner before proceeding to use those applications or websites.

- **`p107.s1`** · _Your Consent_ · matched: we collect
  > ‹prev› Your Consent
  > **We process your Personal Information with consent.**
  > ‹next› By using the PhonePe Platform or services and/or by providing your Personal Information, you consent to the processing of your Personal Information by PhonePe in accordance with this Privacy Policy.

---

## G2 `third_party_advertising_tracking` (exposure, weight 3)

**Question:** Does the company sell personal data, or share it with / let third parties collect it for advertising, marketing or cross-site tracking?

**Searches run** (sentences matched):  
advertis* [core]: **2**; targeted / interest-based / behavioural ads [core]: **0**; sell / sale of data [core]: **1**; pixel / SDK / tracking tech [core]: **0**; ad / marketing partners [core]: **0**; opt-out of sale/ads / GPC [core]: **0**; cookies [support]: **13**; analytics provider [support]: **0**; share with third parties [support]: **2**; marketing [support]: **5**

Terms with no hits: targeted / interest-based / behavioural ads, pixel / SDK / tracking tech, ad / marketing partners, opt-out of sale/ads / GPC, analytics provider

**Candidates:** 4 found, 4 shown

- **`p057.s1`** · _Purpose and Use of Information_ · matched: sell / sale of data
  > ‹prev› to process payments on your behalf and on your instructions; communicate with you for your queries, transactions, and/or any other regulatory requirement, etc.
  > **to facilitate the offer of services and enable communications to you by WealthBasket curators for purchase and sale transactions of Wealthbaskets by you**
  > ‹next› to authenticate a transaction request; validate a standing instruction for a Systematic Investment Plan or confirm a payment made via the services

- **`p065.s1`** · _Purpose and Use of Information_ · matched: advertis*, marketing (s)
  > ‹prev› enforce our terms and conditions
  > **to inform you about online and offline offers, products, services, and updates; customizing and improving your experience by marketing, presenting advertising, and offering tailored products and offers**
  > ‹next› to resolve disputes; troubleshoot problems; technical support and fixing bugs; help promote a safe service

- **`p073.s1`** · _Cookies or Similar Technologies_ · matched: cookies (s), marketing (s)
  > ‹prev› Cookies or Similar Technologies
  > **We use data collection devices such as “cookies” or similar technologies on certain pages of the Platform to help analyse our web page flow, measure promotional effectiveness, and promote trust and safety.**
  > ‹next› “Cookies” are small files placed on your device hard-drive/storage that assist us in providing our services.

- **`p089.s1`** · _Information Sharing and Disclosures_ · matched: advertis*
  > ‹prev› enforce our Terms or Privacy Policy;
  > **respond to claims that an advertisement, posting, or other content violates the rights of a third party; or protect the rights, property or personal safety of our users or the general public**
  > ‹next› if required to do so by law or in good faith where we believe that such disclosure is reasonably necessary to respond to subpoenas, court orders, or other legal process

---

## G3 `profiling_automated_decisions` (exposure, weight 2)

**Question:** Does the company build profiles or inferences about users, or make automated decisions about them?

**Searches run** (sentences matched):  
profiling [core]: **1**; automated decision [core]: **0**; infer / inference [core]: **0**; legal or similarly significant [core]: **0**; scoring [core]: **3**; personalise / recommend [support]: **2**; interests / preferences / segments [support]: **2**; predict / analyse behaviour [support]: **1**

Terms with no hits: automated decision, infer / inference, legal or similarly significant

**Candidates:** 4 found, 4 shown

- **`p038.s2`** · _Information Collection_ · matched: profiling
  > ‹prev› creating your PhonePe user account.
  > **Your associated profile information, including but not limited to name, email id, other profile details as may be provided by you, will be common across PhonePe apps**
  > ‹next› transacting or attempting to transact on PhonePe Platform

- **`p045.s1`** · _Information Collection_ · matched: scoring
  > ‹prev› financial history and other information for the purpose of providing you PhonePe services, verifying and authenticating an investment transaction request you place with us to prevent suspicious transactions, or to comply with court judgements and bankruptcies, from credit reference and fraud prevention agencies.
  > **your credit information from credit bureaus including credit reports, credit scores and other related information, if any**
  > ‹next› vehicle-related information

- **`p086.s2`** · _Information Sharing and Disclosures_ · matched: scoring
  > ‹prev› if it is required by financial institutions or our business partners to determine your credit eligibility.
  > **Note that such financial institutions or business partners, including lending partners, may pull your information from credit bureaus for eligibility determination and risk assessment**
  > ‹next› for services related to communication, marketing, data and information storage, transmission, security, analytics, fraud detection, risk assessment and research

- **`p087.s1`** · _Information Sharing and Disclosures_ · matched: scoring
  > ‹prev› Note that such financial institutions or business partners, including lending partners, may pull your information from credit bureaus for eligibility determination and risk assessment
  > **for services related to communication, marketing, data and information storage, transmission, security, analytics, fraud detection, risk assessment and research**
  > ‹next› enforce our Terms or Privacy Policy;

---

## G4 `data_retention_specificity` (governance, weight 2)

**Question:** How specific is the policy about how long personal data is kept?

**Searches run** (sentences matched):  
retain / retention [core]: **7**; keep / store for [core]: **1**; as long as necessary [core]: **1**; numeric period [core]: **2**; indefinitely [core]: **0**; delete after / deletion [support]: **5**; legal obligation [support]: **5**

Terms with no hits: indefinitely

**Candidates:** 10 found, 10 shown

- **`p008.s1`** · _Storage and Retention_ · matched: retain / retention
  > ‹prev› Information Sharing and Disclosures
  > **Storage and Retention**
  > ‹next› Reasonable Security Practices

- **`p032.s1`** · _Information Collection_ · matched: keep / store for
  > ‹prev› your device details such as device identifier, internet bandwidth, mobile device model, browser plug-ins, and cookies or similar technologies that may identify your browser/PhonePe Applications and plug-ins, and time spent, IP address and location
  > **your Short Messaging Service (SMS(es)) that are stored on your device for the purposes of, including but not limited to, registering you and your device for payments or investment services, OTPs for logins and payments, enhancing your security, bill payments and recharge reminders, and any other legitimate uses with your explicit consent**
  > ‹next› your health and lifestyle-related information, including your physical activity, when you opt for health-tracking services

- **`p096.s1`** · _Storage and Retention_ · matched: retain / retention
  > ‹prev› We do not accept any responsibility or liability for usage of your Personal Information by these third parties or their policies.
  > **Storage and Retention**
  > ‹next› To the extent applicable, we store Personal Information within India and retain it in accordance with applicable laws and for a period no longer than it is required for the purpose for which it was collected.

- **`p097.s1`** · _Storage and Retention_ · matched: retain / retention, as long as necessary
  > ‹prev› Storage and Retention
  > **To the extent applicable, we store Personal Information within India and retain it in accordance with applicable laws and for a period no longer than it is required for the purpose for which it was collected.**
  > ‹next› However, we may retain Personal Information related to you if we believe it may be necessary to prevent fraud or future abuse or if required by law such as in the event of the pendency of any legal/regulatory proceeding or receipt of any legal and/or regulatory direction to that effect or for other legitimate purposes.

- **`p097.s2`** · _Storage and Retention_ · matched: retain / retention, legal obligation (s)
  > ‹prev› To the extent applicable, we store Personal Information within India and retain it in accordance with applicable laws and for a period no longer than it is required for the purpose for which it was collected.
  > **However, we may retain Personal Information related to you if we believe it may be necessary to prevent fraud or future abuse or if required by law such as in the event of the pendency of any legal/regulatory proceeding or receipt of any legal and/or regulatory direction to that effect or for other legitimate purposes.**
  > ‹next› Once the Personal Information has reached its retention period, it shall be deleted in compliance with applicable laws.

- **`p098.s1`** · _Storage and Retention_ · matched: retain / retention, delete after / deletion (s)
  > ‹prev› However, we may retain Personal Information related to you if we believe it may be necessary to prevent fraud or future abuse or if required by law such as in the event of the pendency of any legal/regulatory proceeding or receipt of any legal and/or regulatory direction to that effect or for other legitimate purposes.
  > **Once the Personal Information has reached its retention period, it shall be deleted in compliance with applicable laws.**
  > ‹next› Reasonable Security Practices

- **`p112.s4`** · _Personal Information Access/Rectification and Consent_ · matched: retain / retention
  > ‹prev› Upon such revocation, you may lose access to services that were availed on the basis of the consent provided.
  > **In some cases, we may continue to retain your information as per the ‘Storage and Retention’ section of this Policy.**
  > ‹next› To raise any of the above requests, you may write to us using the contact information provided under the ‘Contact Us’ section of this Policy.

- **`p113.s2`** · _Personal Information Access/Rectification and Consent_ · matched: retain / retention
  > ‹prev› In case you wish to delete your account or Personal Information, please use the ‘Help’ section of the PhonePe Platform.
  > **However, retention of your Personal Information will be subject to applicable laws.**
  > ‹next› For the above requests, PhonePe may need to request specific information from you to confirm your identity and ensure authentication.

- **`p117.s2`** · _Children Information_ · matched: numeric period
  > ‹prev› We do not knowingly solicit or collect Personal Information from children under the age of 18 and use of our Platform is available only to persons who can form a legally binding contract under the Indian Contract Act, 1872.
  > **If you are under the age of 18 years then you must use the Platform or services under the supervision of your parent, legal guardian, or any responsible adult.**
  > ‹next› Changes to Policy

- **`p158.s1`** · _Supported capabilities_ · matched: numeric period
  > ‹prev› Do not provide medical records or policy credentials.
  > **Try: Show me health insurance options for a 30-year-old in a tier 1 city.**
  > ‹next› Health-plan comparison:

---

## G5 `user_rights_access_deletion` (governance, weight 2)

**Question:** What rights do users have to access, correct and delete their data, and for whom?

**Searches run** (sentences matched):  
right to / your rights [core]: **2**; access [core]: **1**; correct / rectify / update [core]: **2**; delete / erase [core]: **2**; portability / export [core]: **0**; object / restrict [support]: **0**; nominate (DPDP) [support]: **0**; jurisdiction limits [support]: **0**

Terms with no hits: portability / export, object / restrict, nominate (DPDP), jurisdiction limits

**Candidates:** 7 found, 7 shown

- **`p013.s1`** · _Personal Information Access/Rectification and Consent_ · matched: correct / rectify / update
  > ‹prev› Choice/Opt-out
  > **Personal Information Access/Rectification and Consent**
  > ‹next› Children Information

- **`p073.s8`** · _Cookies or Similar Technologies_ · matched: delete / erase
  > ‹prev› Most cookies are “session cookies,” meaning that they are automatically deleted from your device hard-drive/storage at the end of a session.
  > **You are always free to decline/delete our cookies or similar technologies if your browser/device permits, although in that case you may not be able to use certain features on the Platform and you may be required to re-enter your password more frequently during a session.**
  > ‹next› Additionally, you may encounter “cookies” or other similar technologies on certain pages of the Platform that are placed by third parties.

- **`p089.s1`** · _Information Sharing and Disclosures_ · matched: right to / your rights
  > ‹prev› enforce our Terms or Privacy Policy;
  > **respond to claims that an advertisement, posting, or other content violates the rights of a third party; or protect the rights, property or personal safety of our users or the general public**
  > ‹next› if required to do so by law or in good faith where we believe that such disclosure is reasonably necessary to respond to subpoenas, court orders, or other legal process

- **`p111.s1`** · _Personal Information Access/Rectification and Consent_ · matched: correct / rectify / update
  > ‹prev› In case you receive a call for any specific PhonePe product/service you may opt-out from such calls by informing PhonePe’s representative during the call.
  > **Personal Information Access/Rectification and Consent**
  > ‹next› You can access and review your Personal Information shared by you by placing a request with us.

- **`p113.s1`** · _Personal Information Access/Rectification and Consent_ · matched: delete / erase
  > ‹prev› To raise any of the above requests, you may write to us using the contact information provided under the ‘Contact Us’ section of this Policy.
  > **In case you wish to delete your account or Personal Information, please use the ‘Help’ section of the PhonePe Platform.**
  > ‹next› However, retention of your Personal Information will be subject to applicable laws.

- **`p114.s2`** · _Personal Information Access/Rectification and Consent_ · matched: right to / your rights
  > ‹prev› For the above requests, PhonePe may need to request specific information from you to confirm your identity and ensure authentication.
  > **This is a security measure to ensure that Personal Information is not disclosed to any person who does not have a right to receive it or is not incorrectly modified or deleted.**
  > ‹next› In cases where you need any further information specific to the product/ services that you are availing, we request you to read through the Terms and Conditions specific to the product/service which is easily accessible through the PhonePe Platform.

- **`p186.s2`** · _Supported capabilities_ · matched: access
  > ‹prev› The connector receives the selected MCP tool, supplied arguments, and technical metadata needed to deliver and protect the service.
  > **PhonePe does not request access to the host’s full chat history, memory, conversation summaries, unrelated uploads, or unrelated conversation content.**
  > ‹next› Provide only task-specific information in tool inputs.

---

## G6 `international_data_transfers` (exposure, weight 1)

**Question:** Is personal data transferred to or stored in other countries, and are safeguards named?

**Searches run** (sentences matched):  
transfer [core]: **4**; cross-border / international [core]: **2**; stored / processed in a country [core]: **0**; safeguard mechanisms [core]: **0**; localisation [core]: **0**; servers [support]: **3**; jurisdiction [support]: **2**

Terms with no hits: stored / processed in a country, safeguard mechanisms, localisation

**Candidates:** 6 found, 6 shown

- **`p023.s1`** · _Updated 15 May 2026_ · matched: transfer
  > ‹prev› We value the trust you place in us and respect your privacy, maintaining the highest standards for secure transactions and protection of your personal information.
  > **This Privacy Policy is published and shall be construed in accordance with the provisions of Indian laws and regulations including the Information Technology (Reasonable Security Practices and Procedures and Sensitive Personal Data or Information) Rules, 2011 under the Information Technology Act, 2000, the Aadhaar Act, 2016 and its Amendments, including the Aadhaar Regulations; that require publishing of the privacy policy for collection, use, storage, transfer, disclosure of Personal Information.**
  > ‹next› Personal Information means and includes all information that can be linked to a specific individual and also includes Sensitive Personal Information (all Personal Information which requires heightened data protection measures due to its sensitive and personal nature), both, hereinafter referred to as “Personal Information”, excluding any information that is freely available or accessible in public domain.

- **`p068.s1`** · _Purpose and Use of Information_ · matched: cross-border / international, jurisdiction (s)
  > ‹prev› training our representatives and agents for ensuring quality of support/advice provided during your interactions with us
  > **to identify security breaches and attacks; investigating, preventing, and taking action on illegal or suspected fraud or money laundering activities and conducting forensic audits as part of internal or external audit or investigation by PhonePe or government agencies located within India or outside the Indian jurisdiction**
  > ‹next› to meet legal and regulatory obligations

- **`p093.s1`** · _Information Sharing and Disclosures_ · matched: cross-border / international, jurisdiction (s)
  > ‹prev› for grievance redressal and resolution of disputes
  > **with the internal investigation department within PhonePe or agencies appointed by PhonePe for investigation purposes located within or outside the Indian jurisdiction**
  > ‹next› should we (or our assets) plan to merge with, or be acquired by any business entity, or re-organization, amalgamation, restructuring of our business then with such other business entity

- **`p122.s7`** · _PhonePe MCP Data Use Policy_ · matched: transfer
  > ‹prev› The Connector processes your search queries for informational purposes only.
  > **It will not execute money transfers, place investment orders, bind insurance policies, make payments, or submit applications for loans or credit cards.**
  > ‹next› Technical and operational information:

- **`p132.s1`** · _PhonePe MCP Documentation_ · matched: transfer
  > ‹prev› The connector can show informational lending and insurance options, compare supported health plans, discover and compare mutual funds, present general investment categories, and locate supported destinations in the PhonePe app.
  > **Read-only The connector does not transfer money, place an investment order, bind an insurance policy, make a payment, or submit a loan or credit-card application.**
  > ‹next› When a user chooses to continue, the connector may present a PhonePe link.

- **`p196.s1`** · _Supported capabilities_ · matched: transfer
  > ‹prev› • The connector does not provide emergency or medical advice.
  > **• The connector does not execute a payment or other asset transfer.**
  > ‹next› Troubleshooting

---

## G7 `childrens_data_safeguards` (governance, weight 2)

**Question:** What does the policy say about children and minors, and what age threshold and safeguards apply?

**Searches run** (sentences matched):  
child / children / minor [core]: **3**; age threshold [core]: **2**; parent / guardian / consent [core]: **1**; COPPA / age verification [core]: **0**; knowingly collect [support]: **1**

Terms with no hits: COPPA / age verification

**Candidates:** 4 found, 4 shown

- **`p014.s1`** · _Children Information_ · matched: child / children / minor
  > ‹prev› Personal Information Access/Rectification and Consent
  > **Children Information**
  > ‹next› Changes to Policy

- **`p116.s1`** · _Children Information_ · matched: child / children / minor
  > ‹prev› For seeking any further information on the same, you can write to us at the details mentioned in the ‘Contact Us’ section of this Policy.
  > **Children Information**
  > ‹next› We do not knowingly solicit or collect Personal Information from children under the age of 18 and use of our Platform is available only to persons who can form a legally binding contract under the Indian Contract Act, 1872.

- **`p117.s1`** · _Children Information_ · matched: child / children / minor, age threshold, knowingly collect (s)
  > ‹prev› Children Information
  > **We do not knowingly solicit or collect Personal Information from children under the age of 18 and use of our Platform is available only to persons who can form a legally binding contract under the Indian Contract Act, 1872.**
  > ‹next› If you are under the age of 18 years then you must use the Platform or services under the supervision of your parent, legal guardian, or any responsible adult.

- **`p117.s2`** · _Children Information_ · matched: age threshold, parent / guardian / consent
  > ‹prev› We do not knowingly solicit or collect Personal Information from children under the age of 18 and use of our Platform is available only to persons who can form a legally binding contract under the Indian Contract Act, 1872.
  > **If you are under the age of 18 years then you must use the Platform or services under the supervision of your parent, legal guardian, or any responsible adult.**
  > ‹next› Changes to Policy

---

## AI1 `ai_model_training_on_user_content` (exposure, weight 3)

**Question:** Does the company use users' personal data or content to train or improve AI / machine-learning models?

**Searches run** (sentences matched):  
train / training [core]: **1**; model(s) [core]: **1**; machine learning [core]: **0**; artificial intelligence / AI [core]: **3**; improve / develop services [support]: **0**; content / inputs / outputs [support]: **9**; research [support]: **1**

Terms with no hits: machine learning, improve / develop services

**Candidates:** 5 found, 5 shown

- **`p031.s1`** · _Information Collection_ · matched: model(s)
  > ‹prev› balance including broker ledger balance or margins, transaction history and value, bank account details, wallet balance, investment details and transactions, income range, expense range, investment goals, service or transaction related communication, order details, service fulfilment details, part of your card details for smooth transaction using PhonePe or any of the services
  > **your device details such as device identifier, internet bandwidth, mobile device model, browser plug-ins, and cookies or similar technologies that may identify your browser/PhonePe Applications and plug-ins, and time spent, IP address and location**
  > ‹next› your Short Messaging Service (SMS(es)) that are stored on your device for the purposes of, including but not limited to, registering you and your device for payments or investment services, OTPs for logins and payments, enhancing your security, bill payments and recharge reminders, and any other legitimate uses with your explicit consent

- **`p067.s1`** · _Purpose and Use of Information_ · matched: train / training
  > ‹prev› to resolve disputes; troubleshoot problems; technical support and fixing bugs; help promote a safe service
  > **training our representatives and agents for ensuring quality of support/advice provided during your interactions with us**
  > ‹next› to identify security breaches and attacks; investigating, preventing, and taking action on illegal or suspected fraud or money laundering activities and conducting forensic audits as part of internal or external audit or investigation by PhonePe or government agencies located within India or outside the Indian jurisdiction

- **`p131.s1`** · _PhonePe MCP Documentation_ · matched: artificial intelligence / AI, content / inputs / outputs (s)
  > ‹prev› Overview:
  > **PhonePe AI Connectors help users explore PhonePe products and destinations from a Claude or ChatGPT conversation.**
  > ‹next› In this guide, the selected platform is called the host.

- **`p186.s4`** · _Supported capabilities_ · matched: artificial intelligence / AI
  > ‹prev› Provide only task-specific information in tool inputs.
  > **Read the PhonePe AI Connectors Privacy Notice, including the disclosures about downstream processing of navigation requests.**
  > ‹next› Links and leaving the host:

- **`p210.s1`** · _Connector privacy notice: PhonePe AI Connectors Privacy Notice_ · matched: artificial intelligence / AI
  > ‹prev› Connector support: support.phonepe.com
  > **Connector privacy notice: PhonePe AI Connectors Privacy Notice**
  > ‹next› PhonePe privacy policy: phonepe.com/privacy-policy

---

## AI2 `ai_training_opt_out_control` (governance, weight 2)

**Question:** If personal data is used for AI training, can the user stop it, and how?

**Searches run** (sentences matched):  
opt out [core]: **4**; turn off / disable [core]: **0**; choose whether / your choices [core]: **0**; settings / controls [support]: **10**; train / model (co-occurrence) [support]: **2**; object / request [support]: **4**

Terms with no hits: turn off / disable, choose whether / your choices

**Candidates:** 4 found, 4 shown

- **`p012.s1`** · _Choice/Opt-out_ · matched: opt out
  > ‹prev› Your Consent
  > **Choice/Opt-out**
  > ‹next› Personal Information Access/Rectification and Consent

- **`p108.s1`** · _Choice/Opt-out_ · matched: opt out
  > ‹prev› Further, you agree and authorize PhonePe to communicate with you via channels like Phone calls and E-mail for the purposes set out in this policy, irrespective of your registration with any authorized DND registries.
  > **Choice/Opt-out**
  > ‹next› We provide all users with the opportunity to opt-out of receiving any of our services or non-essential (promotional, marketing-related) communications from us, after setting up an account.

- **`p109.s1`** · _Choice/Opt-out_ · matched: opt out
  > ‹prev› Choice/Opt-out
  > **We provide all users with the opportunity to opt-out of receiving any of our services or non-essential (promotional, marketing-related) communications from us, after setting up an account.**
  > ‹next› If you want to remove your contact information from all our lists and newsletters or discontinue any of our services, please click on the unsubscribe button on the emailers.

- **`p110.s1`** · _Choice/Opt-out_ · matched: opt out
  > ‹prev› If you want to remove your contact information from all our lists and newsletters or discontinue any of our services, please click on the unsubscribe button on the emailers.
  > **In case you receive a call for any specific PhonePe product/service you may opt-out from such calls by informing PhonePe’s representative during the call.**
  > ‹next› Personal Information Access/Rectification and Consent

---

## AI3 `ai_human_review_of_chats` (exposure, weight 2)

**Question:** Can people (employees, contractors, reviewers) read or review users' content?

**Searches run** (sentences matched):  
human review [core]: **0**; reviewers / annotators / moderators [core]: **0**; staff may access / review content [core]: **0**; review content / conversations [core]: **0**; we may access / review / monitor content [core]: **0**; flagged / safety / abuse [support]: **3**; support / feedback [support]: **1**

Terms with no hits: human review, reviewers / annotators / moderators, staff may access / review content, review content / conversations, we may access / review / monitor content

**Candidates:** 0 found, 0 shown

_No candidate sentences. Before labelling Absent, scan the headings in the numbered text._

---

## AI4 `deidentification_training_carveout` (exposure, weight 2)

**Question:** Does the policy let the company keep, use or share de-identified or aggregated data, and for what?

**Searches run** (sentences matched):  
de-identified [core]: **0**; anonymised [core]: **0**; aggregated [core]: **1**; pseudonymised [core]: **0**; no longer identifies [core]: **0**; share / any purpose [support]: **18**

Terms with no hits: de-identified, anonymised, pseudonymised, no longer identifies

**Candidates:** 1 found, 1 shown

- **`p059.s1`** · _Purpose and Use of Information_ · matched: aggregated
  > ‹prev› to authenticate a transaction request; validate a standing instruction for a Systematic Investment Plan or confirm a payment made via the services
  > **enhancing your user experience in various processes/submission of applications/availment of product/service offerings by analysing user behaviour on an aggregated basis**
  > ‹next› simplifying and enabling your user journey, where applicable, using data we may have about you

---

## AI5 `third_party_ai_subprocessors` (exposure, weight 2)

**Question:** Is user content sent to external AI / model providers, or licensed to others for AI training?

**Searches run** (sentences matched):  
AI / model providers [core]: **0**; named AI vendors [core]: **13**; third-party AI / models [core]: **0**; integrations / connectors / plugins [core]: **38**; license content / data licensing [core]: **0**; sub-processors / service providers [support]: **6**; AI features [support]: **0**

Terms with no hits: AI / model providers, third-party AI / models, license content / data licensing, AI features

**Candidates:** 45 found, 20 shown (the rest are in `P12_phonepe_evidence.json`)

- **`p016.s1`** · _PhonePe MCP Data Use Policy_ · matched: integrations / connectors / plugins
  > ‹prev› Changes to Policy
  > **PhonePe MCP Data Use Policy**
  > ‹next› PhonePe MCP Documentation

- **`p017.s1`** · _PhonePe MCP Documentation_ · matched: integrations / connectors / plugins
  > ‹prev› PhonePe MCP Data Use Policy
  > **PhonePe MCP Documentation**
  > ‹next› Contact Us

- **`p031.s1`** · _Information Collection_ · matched: integrations / connectors / plugins
  > ‹prev› balance including broker ledger balance or margins, transaction history and value, bank account details, wallet balance, investment details and transactions, income range, expense range, investment goals, service or transaction related communication, order details, service fulfilment details, part of your card details for smooth transaction using PhonePe or any of the services
  > **your device details such as device identifier, internet bandwidth, mobile device model, browser plug-ins, and cookies or similar technologies that may identify your browser/PhonePe Applications and plug-ins, and time spent, IP address and location**
  > ‹next› your Short Messaging Service (SMS(es)) that are stored on your device for the purposes of, including but not limited to, registering you and your device for payments or investment services, OTPs for logins and payments, enhancing your security, bill payments and recharge reminders, and any other legitimate uses with your explicit consent

- **`p067.s1`** · _Purpose and Use of Information_ · matched: integrations / connectors / plugins
  > ‹prev› to resolve disputes; troubleshoot problems; technical support and fixing bugs; help promote a safe service
  > **training our representatives and agents for ensuring quality of support/advice provided during your interactions with us**
  > ‹next› to identify security breaches and attacks; investigating, preventing, and taking action on illegal or suspected fraud or money laundering activities and conducting forensic audits as part of internal or external audit or investigation by PhonePe or government agencies located within India or outside the Indian jurisdiction

- **`p120.s1`** · _PhonePe MCP Data Use Policy_ · matched: integrations / connectors / plugins
  > ‹prev› We will never make changes to policies in order to make it less protective of Personal Information already shared by you.
  > **PhonePe MCP Data Use Policy**
  > ‹next› Scope:

- **`p122.s1`** · _PhonePe MCP Data Use Policy_ · matched: named AI vendors, integrations / connectors / plugins
  > ‹prev› Scope:
  > **This notice outlines how PhonePe Limited handles your information when you interact with the PhonePe connector in Claude and ChatGPT (the Connector).**
  > ‹next› Please refer to PhonePe Privacy Policy for complete information on how PhonePe handles your personal information.

- **`p122.s3`** · _PhonePe MCP Data Use Policy_ · matched: integrations / connectors / plugins
  > ‹prev› Please refer to PhonePe Privacy Policy for complete information on how PhonePe handles your personal information.
  > **The Connector may display links hosted on PhonePe’s short-link domain ( https://phon.pe).**
  > ‹next› Opening these links will redirect you from the Connector to the PhonePe interface where actions are subject to the applicable product TnC’s and the PhonePe Privacy Policy.

- **`p122.s4`** · _PhonePe MCP Data Use Policy_ · matched: integrations / connectors / plugins
  > ‹prev› The Connector may display links hosted on PhonePe’s short-link domain ( https://phon.pe).
  > **Opening these links will redirect you from the Connector to the PhonePe interface where actions are subject to the applicable product TnC’s and the PhonePe Privacy Policy.**
  > ‹next› The Connector helps users explore selected PhonePe products and services by providing general information, links and destinations.

- **`p122.s5`** · _PhonePe MCP Data Use Policy_ · matched: integrations / connectors / plugins
  > ‹prev› Opening these links will redirect you from the Connector to the PhonePe interface where actions are subject to the applicable product TnC’s and the PhonePe Privacy Policy.
  > **The Connector helps users explore selected PhonePe products and services by providing general information, links and destinations.**
  > ‹next› The Connector processes your search queries for informational purposes only.

- **`p122.s6`** · _PhonePe MCP Data Use Policy_ · matched: integrations / connectors / plugins
  > ‹prev› The Connector helps users explore selected PhonePe products and services by providing general information, links and destinations.
  > **The Connector processes your search queries for informational purposes only.**
  > ‹next› It will not execute money transfers, place investment orders, bind insurance policies, make payments, or submit applications for loans or credit cards.

- **`p124.s1`** · _PhonePe MCP Data Use Policy_ · matched: integrations / connectors / plugins
  > ‹prev› Technical and operational information:
  > **Systems used to deliver and protect the Connector may process technical data such as timestamps, generated request or session identifiers, service status, error details, IP address, user agent, and security or diagnostic events.**
  > ‹next› To ensure your information remains secure, avoid sharing your personal data such as your name, email-id, bank account or card numbers, UPI PIN, OTPs, passwords, authentication tokens, government identifiers, transaction logs, or medical data while using the PhonePe Connector in Claude.

- **`p124.s2`** · _PhonePe MCP Data Use Policy_ · matched: named AI vendors, integrations / connectors / plugins
  > ‹prev› Systems used to deliver and protect the Connector may process technical data such as timestamps, generated request or session identifiers, service status, error details, IP address, user agent, and security or diagnostic events.
  > **To ensure your information remains secure, avoid sharing your personal data such as your name, email-id, bank account or card numbers, UPI PIN, OTPs, passwords, authentication tokens, government identifiers, transaction logs, or medical data while using the PhonePe Connector in Claude.**
  > ‹next› The PhonePe Connector does not request or require this information to function.

- **`p124.s3`** · _PhonePe MCP Data Use Policy_ · matched: integrations / connectors / plugins
  > ‹prev› To ensure your information remains secure, avoid sharing your personal data such as your name, email-id, bank account or card numbers, UPI PIN, OTPs, passwords, authentication tokens, government identifiers, transaction logs, or medical data while using the PhonePe Connector in Claude.
  > **The PhonePe Connector does not request or require this information to function.**
  > ‹next› How information is used:

- **`p126.s1`** · _PhonePe MCP Data Use Policy_ · matched: integrations / connectors / plugins
  > ‹prev› How information is used:
  > **PhonePe processes Connector information solely to fulfill your search requests and present interactive search results, retrieve and format relevant product details, resolve navigation requests to PhonePe and comply with applicable legal, regulatory, audit, and statutory requirements.**
  > ‹next› Contact:

- **`p128.s1`** · _PhonePe MCP Data Use Policy_ · matched: integrations / connectors / plugins
  > ‹prev› Contact:
  > **For any Privacy questions, rights requests or any technical support reach out to us on [email protected] for Connector.**
  > ‹next› PhonePe MCP Documentation

- **`p129.s1`** · _PhonePe MCP Documentation_ · matched: integrations / connectors / plugins
  > ‹prev› For any Privacy questions, rights requests or any technical support reach out to us on [email protected] for Connector.
  > **PhonePe MCP Documentation**
  > ‹next› Overview:

- **`p131.s1`** · _PhonePe MCP Documentation_ · matched: named AI vendors, integrations / connectors / plugins
  > ‹prev› Overview:
  > **PhonePe AI Connectors help users explore PhonePe products and destinations from a Claude or ChatGPT conversation.**
  > ‹next› In this guide, the selected platform is called the host.

- **`p134.s1`** · _PhonePe MCP Documentation_ · matched: named AI vendors, integrations / connectors / plugins
  > ‹prev› Prerequisites and availability:
  > **• A Claude or ChatGPT account with access to the relevant connector or app feature.**
  > ‹next› • If you use a managed workspace, your administrator may need to allow the integration.

- **`p141.s2`** · _PhonePe MCP Documentation_ · matched: named AI vendors, integrations / connectors / plugins
  > ‹prev› 1.
  > **Open Settings in Claude and navigate to Connectors.**
  > ‹next› 2.

- **`p146.s2`** · _PhonePe MCP Documentation_ · matched: named AI vendors, integrations / connectors / plugins
  > ‹prev› 1.
  > **Open the app or plugin directory available in your ChatGPT account.**
  > ‹next› 2.

---

## DPDP1 `dpdp_unambiguous_affirmative_consent` (readiness, weight 2)

**Question:** How does the policy obtain consent: an explicit affirmative action, a general agreement, or browsewrap ('by using you agree')?

**Searches run** (sentences matched):  
by using / visiting you agree [core]: **1**; consent [core]: **10**; agree / accept [core]: **6**; DPDP / Indian law [core]: **1**; legal basis [core]: **0**; notice / checkbox / sign-up [support]: **8**; explicit / affirmative / freely [support]: **3**

Terms with no hits: legal basis

**Candidates:** 17 found, 17 shown

- **`p011.s1`** · _Your Consent_ · matched: consent
  > ‹prev› Third-Party Products, Services, or Websites
  > **Your Consent**
  > ‹next› Choice/Opt-out

- **`p013.s1`** · _Personal Information Access/Rectification and Consent_ · matched: consent
  > ‹prev› Choice/Opt-out
  > **Personal Information Access/Rectification and Consent**
  > ‹next› Children Information

- **`p022.s2`** · _Updated 15 May 2026_ · matched: agree / accept
  > ‹prev› This policy describes how PhonePe collects, stores, uses and otherwise processes your Personal Information through PhonePe websites, PhonePe Applications, m-sites, chatbots, notifications, interacting with our content on any other site, or any other medium used by PhonePe to provide its services to you (hereinafter referred to as the “Platform”).
  > **By visiting, downloading, using PhonePe Platform, and/or, providing your information or availing our product/services, you expressly agree to be bound by this Privacy Policy (“Policy”) and the applicable service/product terms and conditions.**
  > ‹next› We value the trust you place in us and respect your privacy, maintaining the highest standards for secure transactions and protection of your personal information.

- **`p023.s1`** · _Updated 15 May 2026_ · matched: DPDP / Indian law
  > ‹prev› We value the trust you place in us and respect your privacy, maintaining the highest standards for secure transactions and protection of your personal information.
  > **This Privacy Policy is published and shall be construed in accordance with the provisions of Indian laws and regulations including the Information Technology (Reasonable Security Practices and Procedures and Sensitive Personal Data or Information) Rules, 2011 under the Information Technology Act, 2000, the Aadhaar Act, 2016 and its Amendments, including the Aadhaar Regulations; that require publishing of the privacy policy for collection, use, storage, transfer, disclosure of Personal Information.**
  > ‹next› Personal Information means and includes all information that can be linked to a specific individual and also includes Sensitive Personal Information (all Personal Information which requires heightened data protection measures due to its sensitive and personal nature), both, hereinafter referred to as “Personal Information”, excluding any information that is freely available or accessible in public domain.

- **`p023.s4`** · _Updated 15 May 2026_ · matched: agree / accept
  > ‹prev› Please note, your Personal Information processing will be subject to Indian laws.
  > **If you do not agree with this Privacy Policy, please do not use or access our Platform.**
  > ‹next› Information Collection

- **`p032.s1`** · _Information Collection_ · matched: consent, explicit / affirmative / freely (s)
  > ‹prev› your device details such as device identifier, internet bandwidth, mobile device model, browser plug-ins, and cookies or similar technologies that may identify your browser/PhonePe Applications and plug-ins, and time spent, IP address and location
  > **your Short Messaging Service (SMS(es)) that are stored on your device for the purposes of, including but not limited to, registering you and your device for payments or investment services, OTPs for logins and payments, enhancing your security, bill payments and recharge reminders, and any other legitimate uses with your explicit consent**
  > ‹next› your health and lifestyle-related information, including your physical activity, when you opt for health-tracking services

- **`p034.s1`** · _Information Collection_ · matched: consent, explicit / affirmative / freely (s)
  > ‹prev› your health and lifestyle-related information, including your physical activity, when you opt for health-tracking services
  > **video, photo, audio, and location, based on your explicit consent through your app permissions (camera, microphone, location) when you opt for a product whose core functionality can be delivered only after accessing your app permissions, or where access is as per regulatory requirements, e.g., video-based KYC, self-inspection of your vehicle, and onboarding**
  > ‹next› Information may be collected at various stages of your usage of the PhonePe Platform such as:

- **`p095.s4`** · _Information Sharing and Disclosures_ · matched: agree / accept
  > ‹prev› However, PhonePe may share Personal Information with third-parties such as legally recognized authorities, regulatory bodies, governmental authorities, and financial institutions as per purposes set out in this Policy or as per applicable laws.
  > **We do not accept any responsibility or liability for usage of your Personal Information by these third parties or their policies.**
  > ‹next› Storage and Retention

- **`p105.s5`** · _Third-Party Products, Services, or Websites_ · matched: agree / accept
  > ‹prev› That policy may differ from ours and you are requested to review those policies or seek access to the policies from the domain owner before proceeding to use those applications or websites.
  > **We do not accept any responsibility or liability for usage of your Personal Information by these third parties or their policies.**
  > ‹next› Your Consent

- **`p106.s1`** · _Your Consent_ · matched: consent
  > ‹prev› We do not accept any responsibility or liability for usage of your Personal Information by these third parties or their policies.
  > **Your Consent**
  > ‹next› We process your Personal Information with consent.

- **`p107.s1`** · _Your Consent_ · matched: consent
  > ‹prev› Your Consent
  > **We process your Personal Information with consent.**
  > ‹next› By using the PhonePe Platform or services and/or by providing your Personal Information, you consent to the processing of your Personal Information by PhonePe in accordance with this Privacy Policy.

- **`p107.s2`** · _Your Consent_ · matched: by using / visiting you agree, consent
  > ‹prev› We process your Personal Information with consent.
  > **By using the PhonePe Platform or services and/or by providing your Personal Information, you consent to the processing of your Personal Information by PhonePe in accordance with this Privacy Policy.**
  > ‹next› If you disclose to us any Personal Information relating to other people, you represent that you have the authority to do so and permit us to use the information in accordance with this Privacy Policy.

- **`p107.s4`** · _Your Consent_ · matched: agree / accept, notice / checkbox / sign-up (s)
  > ‹prev› If you disclose to us any Personal Information relating to other people, you represent that you have the authority to do so and permit us to use the information in accordance with this Privacy Policy.
  > **Further, you agree and authorize PhonePe to communicate with you via channels like Phone calls and E-mail for the purposes set out in this policy, irrespective of your registration with any authorized DND registries.**
  > ‹next› Choice/Opt-out

- **`p111.s1`** · _Personal Information Access/Rectification and Consent_ · matched: consent
  > ‹prev› In case you receive a call for any specific PhonePe product/service you may opt-out from such calls by informing PhonePe’s representative during the call.
  > **Personal Information Access/Rectification and Consent**
  > ‹next› You can access and review your Personal Information shared by you by placing a request with us.

- **`p112.s2`** · _Personal Information Access/Rectification and Consent_ · matched: consent
  > ‹prev› You can access and review your Personal Information shared by you by placing a request with us.
  > **In addition, you may at any time revoke consent given to us to store your e-KYC information, collected as part of the Aadhaar-based e-KYC process.**
  > ‹next› Upon such revocation, you may lose access to services that were availed on the basis of the consent provided.

- **`p112.s3`** · _Personal Information Access/Rectification and Consent_ · matched: consent
  > ‹prev› In addition, you may at any time revoke consent given to us to store your e-KYC information, collected as part of the Aadhaar-based e-KYC process.
  > **Upon such revocation, you may lose access to services that were availed on the basis of the consent provided.**
  > ‹next› In some cases, we may continue to retain your information as per the ‘Storage and Retention’ section of this Policy.

- **`p119.s4`** · _Changes to Policy_ · matched: agree / accept
  > ‹prev› We may, however, reasonably endeavour to notify you of the changes, it is your responsibility to review the Privacy Policy periodically for updates/changes.
  > **Your continued use of our services/Platform, following the posting of changes will mean that you accept and agree to the revisions.**
  > ‹next› We will never make changes to policies in order to make it less protective of Personal Information already shared by you.

---

## DPDP2 `dpdp_easy_consent_withdrawal` (readiness, weight 2)

**Question:** Can users withdraw consent, and is it as easy as giving it?

**Searches run** (sentences matched):  
withdraw / revoke consent [core]: **2**; consent manager [core]: **0**; opt out / unsubscribe [core]: **5**; settings / dashboard [support]: **4**; contact / email to withdraw [support]: **15**; delete account [support]: **1**; consent (co-occurrence) [support]: **10**

Terms with no hits: consent manager

**Candidates:** 8 found, 8 shown

- **`p012.s1`** · _Choice/Opt-out_ · matched: opt out / unsubscribe
  > ‹prev› Your Consent
  > **Choice/Opt-out**
  > ‹next› Personal Information Access/Rectification and Consent

- **`p108.s1`** · _Choice/Opt-out_ · matched: opt out / unsubscribe
  > ‹prev› Further, you agree and authorize PhonePe to communicate with you via channels like Phone calls and E-mail for the purposes set out in this policy, irrespective of your registration with any authorized DND registries.
  > **Choice/Opt-out**
  > ‹next› We provide all users with the opportunity to opt-out of receiving any of our services or non-essential (promotional, marketing-related) communications from us, after setting up an account.

- **`p109.s1`** · _Choice/Opt-out_ · matched: opt out / unsubscribe
  > ‹prev› Choice/Opt-out
  > **We provide all users with the opportunity to opt-out of receiving any of our services or non-essential (promotional, marketing-related) communications from us, after setting up an account.**
  > ‹next› If you want to remove your contact information from all our lists and newsletters or discontinue any of our services, please click on the unsubscribe button on the emailers.

- **`p109.s2`** · _Choice/Opt-out_ · matched: opt out / unsubscribe, contact / email to withdraw (s)
  > ‹prev› We provide all users with the opportunity to opt-out of receiving any of our services or non-essential (promotional, marketing-related) communications from us, after setting up an account.
  > **If you want to remove your contact information from all our lists and newsletters or discontinue any of our services, please click on the unsubscribe button on the emailers.**
  > ‹next› In case you receive a call for any specific PhonePe product/service you may opt-out from such calls by informing PhonePe’s representative during the call.

- **`p110.s1`** · _Choice/Opt-out_ · matched: opt out / unsubscribe
  > ‹prev› If you want to remove your contact information from all our lists and newsletters or discontinue any of our services, please click on the unsubscribe button on the emailers.
  > **In case you receive a call for any specific PhonePe product/service you may opt-out from such calls by informing PhonePe’s representative during the call.**
  > ‹next› Personal Information Access/Rectification and Consent

- **`p112.s2`** · _Personal Information Access/Rectification and Consent_ · matched: withdraw / revoke consent, consent (co-occurrence) (s)
  > ‹prev› You can access and review your Personal Information shared by you by placing a request with us.
  > **In addition, you may at any time revoke consent given to us to store your e-KYC information, collected as part of the Aadhaar-based e-KYC process.**
  > ‹next› Upon such revocation, you may lose access to services that were availed on the basis of the consent provided.

- **`p112.s3`** · _Personal Information Access/Rectification and Consent_ · matched: withdraw / revoke consent, consent (co-occurrence) (s)
  > ‹prev› In addition, you may at any time revoke consent given to us to store your e-KYC information, collected as part of the Aadhaar-based e-KYC process.
  > **Upon such revocation, you may lose access to services that were availed on the basis of the consent provided.**
  > ‹next› In some cases, we may continue to retain your information as per the ‘Storage and Retention’ section of this Policy.

- **`p201.s2`** · _Troubleshooting_ · matched: settings / dashboard (s), contact / email to withdraw (s)
  > ‹prev› No user access token or PhonePe sign-in is required.
  > **Check your host and workspace settings, retry once, and contact support if the problem persists.**
  > ‹next› Connection restrictions are managed by PhonePe and the host; do not attempt to fix them by sharing credentials, installing certificates, or changing network security settings.

---

## DPDP3 `dpdp_grievance_dpo_contact` (readiness, weight 1)

**Question:** Does the policy publish a Grievance Officer or Data Protection Officer with contact details?

**Searches run** (sentences matched):  
grievance officer [core]: **1**; data protection officer / DPO [core]: **1**; email address [core]: **0**; Data Protection Board / complaint [core]: **0**; contact us [support]: **8**; officer / named person [support]: **1**

Terms with no hits: email address, Data Protection Board / complaint

**Candidates:** 2 found, 2 shown

- **`p092.s1`** · _Information Sharing and Disclosures_ · matched: grievance officer
  > ‹prev› if requested by government authorities for government initiatives and benefits
  > **for grievance redressal and resolution of disputes**
  > ‹next› with the internal investigation department within PhonePe or agencies appointed by PhonePe for investigation purposes located within or outside the Indian jurisdiction

- **`p219.s1`** · _Contact Us_ · matched: data protection officer / DPO, officer / named person (s)
  > ‹prev› Contact Us
  > **In case you have any questions, concerns, or complaints regarding the processing of your Personal Information or this Privacy Policy you may write to PhonePe’s Privacy Officer using this link https://support.phonepe.com We are committed to answer your questions within the reasonable time limit.**
  > ‹next› Any delay in the resolution time shall be proactively communicated to you.

---

## DPDP4 `dpdp_eighth_schedule_languages` (readiness_info, weight 0)

**Question:** Is the notice offered in Indian languages (Eighth Schedule) besides English? Record which languages.

**Searches run** (sentences matched):  
Eighth Schedule [core]: **0**; language(s) / translation [core]: **1**; Indian language names (English) [core]: **0**; Indian language names (native script) [core]: **1**; English [support]: **0**

Terms with no hits: Eighth Schedule, Indian language names (English), English

**Candidates:** 2 found, 2 shown

- **`p002.s1`** · _Englishગુજરાતીதமிழ்తెలుగుमराठीമലയാളംঅসমীয়াবাংলাहिन्दीಕನ್ನಡଓଡ଼ିଆ_ · matched: Indian language names (native script)
  > ‹prev› Privacy policy
  > **Englishગુજરાતીதமிழ்తెలుగుमराठीമലയാളംঅসমীয়াবাংলাहिन्दीಕನ್ನಡଓଡ଼ିଆ**
  > ‹next› Privacy policy

- **`p137.s1`** · _PhonePe MCP Documentation_ · matched: language(s) / translation
  > ‹prev› Some PhonePe destinations require an account after you leave the host.
  > **• Availability depends on the published listing, host account and workspace settings, and applicable regional and age requirements.**
  > ‹next› Individual PhonePe products have their own eligibility requirements.
